"""聊天引擎 — 編排 LLM + ToolCalling + 引用管理。

核心流程：
1. 接收用戶消息 + 歷史對話
2. 構建 system prompt + tool definitions
3. 調用 LLM（支持 function calling 的模型）做工具調用
4. 若 LLM 返回 tool_calls → 執行工具 → 將結果餵回 LLM
5. 重複 3-4 直到 LLM 返回最終文本或達到最大輪數
6. 達到最大輪數或 LLM 返回文本時，用 llm_client.analyze() 做最終總結
   （llm_client 有完整降級鏈，包括 Devin 免費 GLM-5.2-High）

支持流式輸出（SSE）和一次性返回兩種模式。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

import httpx

from app.chat.prompt import CHAT_SYSTEM_PROMPT
from app.chat.registry import init_tools, registry
from app.chat.tool_base import ToolResult
from app.core.llm_client import llm_client
from app.core.providers import PROVIDERS, get_api_key, is_openai_compatible

logger = logging.getLogger("agent.chat.engine")

# 用戶可選的供應商（前端展示用）— 與 AI 策略優化的 8 個供應商完全一致
CHAT_PROVIDERS = [
    "deepseek-pro",      # DeepSeek V4-Pro（推理最強）
    "deepseek-flash",    # DeepSeek V4-Flash（性價比）
    "glm-5.2",           # GLM-5.2（JSON 最穩定）
    "glm-flash",         # GLM-4.5-Flash（免費）
    "qwen",              # Qwen3.6（中文金融最佳）
    "qoder",             # Qoder Lite（免費 SDK）
    "devin",             # Devin GLM-5.2-High（免費 session）
    "ox-alpha",          # OX-Alpha（OpenRouter 推理）
]

# 實際執行工具調用的供應商（必須支持 OpenAI function calling）
# deepseek-flash 是最可靠的選擇（支持 function calling + 可用）
TOOL_CALLING_PROVIDERS = ["deepseek-flash", "glm-5.2", "qwen"]

# 最大工具調用輪數（防止無限循環）
# 複雜金融分析問題需要多輪工具調用（新聞+行情+資金+基本面），5 輪遠不夠
MAX_TOOL_ROUNDS = 100

# 不支持 function calling 的推理模型
REASONING_ONLY_PROVIDERS = {"deepseek-pro"}


@dataclass
class ChatMessage:
    """聊天消息（OpenAI 格式）。"""

    role: str  # system / user / assistant / tool
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None  # 工具名稱（role=tool 時）


@dataclass
class ChatResult:
    """聊天最終結果。"""

    content: str
    provider: str
    model_name: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    tool_calls_log: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0


class ChatEngine:
    """聊天引擎 — 編排 LLM 調用和工具調用循環。"""

    def __init__(self):
        self._tools_initialized = False

    def _ensure_tools(self):
        """延遲初始化工具註冊表。"""
        if not self._tools_initialized:
            init_tools()
            self._tools_initialized = True

    def _get_tool_calling_provider(self) -> str:
        """選擇實際執行工具調用的供應商。

        工具調用需要 OpenAI function calling 支持。
        deepseek-flash 是最可靠的選擇。
        """
        for p in TOOL_CALLING_PROVIDERS:
            if p in PROVIDERS and get_api_key(p) and p not in REASONING_ONLY_PROVIDERS:
                # 快速檢查是否可用（不觸發完整 check_models）
                return p
        return "deepseek-flash"

    def _get_fallback_chain(self, primary: str) -> list[str]:
        """獲取工具調用階段的降級鏈（僅限支持 function calling 的供應商）。"""
        chain = [primary]
        for p in TOOL_CALLING_PROVIDERS:
            if p != primary and p not in REASONING_ONLY_PROVIDERS:
                if p in PROVIDERS and get_api_key(p):
                    chain.append(p)
        return chain

    async def chat(
        self,
        messages: list[ChatMessage],
        provider: str = "",
    ) -> ChatResult:
        """非流式聊天 — 返回完整結果。"""
        self._ensure_tools()

        all_citations: list[dict[str, Any]] = []
        all_tool_logs: list[dict[str, Any]] = []

        openai_messages = self._build_messages(messages)
        tools = registry.to_openai_tools()

        # 工具調用階段：用支持 function calling 的供應商
        tool_provider = self._get_tool_calling_provider()

        for round_idx in range(MAX_TOOL_ROUNDS):
            response = await self._call_llm_with_fallback(
                tool_provider, openai_messages, tools, self._get_fallback_chain(tool_provider)
            )

            if response.get("tool_calls"):
                assistant_msg = response["message"]
                openai_messages.append(assistant_msg)

                for tool_call in response["tool_calls"]:
                    tool_result = await self._execute_tool_call(tool_call)
                    all_citations.extend(tool_result.citations)
                    all_tool_logs.append({
                        "tool": tool_call["function"]["name"],
                        "arguments": tool_call["function"]["arguments"],
                        "success": tool_result.success,
                        "content_preview": tool_result.content[:200],
                    })
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_result.content,
                    })
                continue
            else:
                # LLM 返回了最終文本
                return ChatResult(
                    content=response["content"],
                    provider=tool_provider,
                    model_name=PROVIDERS[tool_provider].model_id,
                    citations=all_citations,
                    tool_calls_log=all_tool_logs,
                    tokens_used=response.get("tokens", 0),
                )

        # 達到最大輪數 — 用 llm_client 做最終總結（有完整降級鏈）
        logger.info(f"[聊天] 達到最大工具調用輪數 {MAX_TOOL_ROUNDS}，用 llm_client 執行最終總結")
        final_content = await self._final_summary_via_llm_client(
            openai_messages, provider, all_citations, all_tool_logs
        )
        return ChatResult(
            content=final_content,
            provider=provider or "devin",
            model_name=PROVIDERS.get(provider or "devin", PROVIDERS["devin"]).model_id,
            citations=all_citations,
            tool_calls_log=all_tool_logs,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        provider: str = "",
    ) -> AsyncGenerator[str, None]:
        """流式聊天 — yield SSE 格式的數據塊。"""
        self._ensure_tools()

        all_citations: list[dict[str, Any]] = []
        all_tool_logs: list[dict[str, Any]] = []

        openai_messages = self._build_messages(messages)
        tools = registry.to_openai_tools()

        tool_provider = self._get_tool_calling_provider()

        for round_idx in range(MAX_TOOL_ROUNDS):
            try:
                response = await self._call_llm_with_fallback(
                    tool_provider, openai_messages, tools, self._get_fallback_chain(tool_provider)
                )
            except Exception as e:
                yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
                return

            if response.get("tool_calls"):
                assistant_msg = response["message"]
                openai_messages.append(assistant_msg)

                for tool_call in response["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    try:
                        args = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}

                    yield json.dumps({
                        "type": "tool_start",
                        "tool": tool_name,
                        "arguments": args,
                    }, ensure_ascii=False)

                    tool_result = await self._execute_tool_call(tool_call)
                    all_citations.extend(tool_result.citations)
                    all_tool_logs.append({
                        "tool": tool_name,
                        "arguments": tool_call["function"]["arguments"],
                        "success": tool_result.success,
                        "content_preview": tool_result.content[:200],
                    })

                    yield json.dumps({
                        "type": "tool_end",
                        "tool": tool_name,
                        "success": tool_result.success,
                        "citations": tool_result.citations,
                        "error": tool_result.error if not tool_result.success else "",
                    }, ensure_ascii=False)

                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_result.content,
                    })

                continue
            else:
                content = response["content"]
                chunk_size = 20
                for i in range(0, len(content), chunk_size):
                    chunk = content[i : i + chunk_size]
                    yield json.dumps({"type": "content", "text": chunk}, ensure_ascii=False)
                    await _async_sleep_ms(30)

                yield json.dumps({
                    "type": "done",
                    "provider": tool_provider,
                    "model": PROVIDERS[tool_provider].model_id,
                    "citations": all_citations,
                    "tool_calls_log": all_tool_logs,
                    "tokens": response.get("tokens", 0),
                }, ensure_ascii=False)
                return

        # 達到最大輪數 — 用 llm_client 做最終總結
        logger.info(f"[聊天] 達到最大工具調用輪數 {MAX_TOOL_ROUNDS}，用 llm_client 執行最終總結")
        try:
            final_content = await self._final_summary_via_llm_client(
                openai_messages, provider, all_citations, all_tool_logs
            )
        except Exception as e:
            yield json.dumps({
                "type": "error",
                "message": f"最終總結失敗: {e}",
            }, ensure_ascii=False)
            return

        # 流式輸出最終總結
        chunk_size = 20
        for i in range(0, len(final_content), chunk_size):
            chunk = final_content[i : i + chunk_size]
            yield json.dumps({"type": "content", "text": chunk}, ensure_ascii=False)
            await _async_sleep_ms(30)

        final_provider = provider or "devin"
        yield json.dumps({
            "type": "done",
            "provider": final_provider,
            "model": PROVIDERS.get(final_provider, PROVIDERS["devin"]).model_id,
            "citations": all_citations,
            "tool_calls_log": all_tool_logs,
            "tokens": 0,
        }, ensure_ascii=False)

    async def _final_summary_via_llm_client(
        self,
        openai_messages: list[dict[str, Any]],
        preferred_provider: str,
        citations: list[dict[str, Any]],
        tool_logs: list[dict[str, Any]],
    ) -> str:
        """用 llm_client.analyze() 做最終總結（有完整降級鏈，包括 Devin 免費 GLM-5.2-High）。

        llm_client 的降級鏈：
        glm-flash → deepseek-flash → qwen → glm-5.2 → deepseek-pro → qoder → devin

        用戶選 "GLM-5.2" 時 preferred_provider="glm-5.2"，如果 glm-5.2 額度耗盡(429)，
        會自動降級到 deepseek-flash → ... → devin（免費 GLM-5.2-High）。
        """
        # 將完整對話歷史（含工具結果）壓縮為一個 prompt
        # 因為 llm_client.analyze() 接受的是 prompt + system_prompt，不是 messages 列表
        prompt_parts: list[str] = []
        for msg in openai_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                continue  # system prompt 單獨傳
            elif role == "user":
                prompt_parts.append(f"【用戶問題】\n{content}")
            elif role == "assistant":
                if content:
                    prompt_parts.append(f"【助手分析】\n{content}")
            elif role == "tool":
                tool_name = msg.get("name", "工具")
                prompt_parts.append(f"【工具結果 - {tool_name}】\n{content}")

        # 添加引用來源摘要
        if citations:
            citation_summary = "\n".join(
                f"- [{c.get('source', '未知')}] {c.get('title', '')} ({c.get('url', '')})"
                for c in citations[:20]  # 最多 20 條
            )
            prompt_parts.append(f"【引用來源】\n{citation_summary}")

        prompt = "\n\n".join(prompt_parts)

        # 構建總結指令
        summary_instruction = (
            "請基於以上對話歷史和工具調用結果，生成一份完整的投研分析報告。"
            "要求：\n"
            "1. 綜合所有工具返回的數據和資訊\n"
            "2. 標註數據來源\n"
            "3. 使用 Markdown 格式，金融數據用表格\n"
            "4. 保持客觀中立，不提供直接買賣建議\n"
            "5. 如有數據缺失，明確說明\n"
        )

        full_prompt = f"{prompt}\n\n---\n{summary_instruction}"

        # 用 llm_client 調用（有完整降級鏈）
        # preferred_provider 映射：用戶選的供應商 → llm_client 的供應商 ID
        llm_preferred = preferred_provider if preferred_provider else ""

        response = await llm_client.analyze(
            prompt=full_prompt,
            system_prompt=CHAT_SYSTEM_PROMPT,
            preferred_provider=llm_preferred,
            json_mode=False,
        )

        logger.info(
            f"[聊天] 最終總結完成: provider={response.provider}, "
            f"fallback_from={response.fallback_from}, duration={response.duration_ms}ms"
        )

        return response.text

    def _build_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        """構建 OpenAI 格式消息列表（含 system prompt）。"""
        result: list[dict[str, Any]] = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
        for msg in messages:
            m: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.name:
                m["name"] = msg.name
            result.append(m)
        return result

    async def _call_llm_with_fallback(
        self,
        primary: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        fallback_chain: list[str],
    ) -> dict[str, Any]:
        """帶降級的 LLM 調用 — 429/401 時自動嘗試下一個供應商。"""
        last_error: Exception | None = None
        for p in fallback_chain:
            try:
                return await self._call_llm_with_tools(p, messages, tools)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                last_error = e
                if status in (429, 401, 403):
                    logger.warning(f"[聊天] 供應商 {p} 返回 {status}，降級到下一個")
                    continue
                logger.warning(f"[聊天] 供應商 {p} 返回 {status}，降級到下一個")
                continue
            except Exception as e:
                last_error = e
                logger.warning(f"[聊天] 供應商 {p} 調用失敗: {e}，降級到下一個")
                continue
        raise RuntimeError(f"所有工具調用供應商均不可用: {last_error}")

    async def _call_llm_with_tools(
        self,
        provider: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """調用 LLM（帶工具定義），返回響應。"""
        info = PROVIDERS[provider]
        api_key = get_api_key(provider)
        if not api_key:
            raise RuntimeError(f"{info.display_name} API key 未配置")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {
            "model": info.model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 8192 if "reasoning" in info.tags else 4096,
        }

        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        url = f"{info.base_url}/chat/completions"
        timeout = 180 if "reasoning" in info.tags else 90

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", 0)

            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError(f"{info.display_name} 返回空 choices")

            choice = choices[0]
            message = choice.get("message", {})
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls")

            if tool_calls:
                return {
                    "content": "",
                    "tool_calls": tool_calls,
                    "message": message,
                    "tokens": tokens,
                }
            else:
                if not content.strip():
                    raise RuntimeError(f"{info.display_name} 返回空字符串")
                return {
                    "content": content.strip(),
                    "tool_calls": None,
                    "message": message,
                    "tokens": tokens,
                }

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> ToolResult:
        """執行單個工具調用。"""
        tool_name = tool_call["function"]["name"]
        try:
            arguments_str = tool_call["function"]["arguments"]
            arguments = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError as e:
            return ToolResult(success=False, content=f"工具參數 JSON 解析失敗: {e}", error=str(e))

        tool = registry.get(tool_name)
        if not tool:
            return ToolResult(success=False, content=f"工具 {tool_name} 不存在", error="tool not found")

        try:
            logger.info(f"[聊天工具] 調用 {tool_name}({arguments})")
            result = await tool.execute(**arguments)
            logger.info(f"[聊天工具] {tool_name} 完成: success={result.success}, citations={len(result.citations)}")
            return result
        except Exception as e:
            logger.error(f"[聊天工具] {tool_name} 執行異常: {e}", exc_info=True)
            return ToolResult(success=False, content=f"工具執行異常: {e}", error=str(e))


async def _async_sleep_ms(ms: int):
    """異步睡眠指定毫秒。"""
    import asyncio

    await asyncio.sleep(ms / 1000.0)


# 全局引擎實例
chat_engine = ChatEngine()
