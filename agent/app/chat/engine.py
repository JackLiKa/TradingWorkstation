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

# 引用壓縮配置 — 避免大量工具調用後 citations_json 超出 DB 列上限
MAX_CITATIONS = 50          # 最多保留 50 條引用（去重後）
MAX_SNIPPET_LENGTH = 200    # 每條引用的 snippet 最多保留 200 字符

# 不支持 function calling 的推理模型
REASONING_ONLY_PROVIDERS = {"deepseek-pro"}

# ===== 安全配置（參考 jnuxky.xyz 安全兜底機制）=====
# 歷史長度截斷 — 服務端保留最後 N 輪，防止 token 耗盡攻擊
MAX_HISTORY_ROUNDS = 10  # 保留最後 10 輪（20 條 user+assistant 消息）
CONTEXT_COMPRESS_THRESHOLD = 12  # 超過此消息數時觸發上下文壓縮
KEEP_RECENT_ROUNDS = 4  # 壓縮時保留最近 4 輪（8 條）原始對話
# 單條消息長度限制 — 防止超長輸入導致 token 耗盡或 DoS
MAX_MESSAGE_LENGTH = 10000  # 每條消息最多 10000 字符
# 客戶端消息角色白名單 — 只接受 user/assistant，拒絕 system/developer/tool
# 防止客戶端注入 system role 覆蓋服務端硬編碼的 system prompt
ALLOWED_CLIENT_ROLES = {"user", "assistant"}


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

    @staticmethod
    def _compress_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """壓縮/提煉引用列表 — 去重 + 截斷 + 限量。

        問題：一次對話可能調用 20+ 次工具（如 open_web_search），每次返回 8 條 citation，
        累計 160+ 條含 title/url/snippet 的引用，JSON 序列化後輕易超過 DB TEXT 列上限（65KB）。
        解決：按 URL 去重 → 截斷 snippet → 限量保留前 MAX_CITATIONS 條。
        """
        seen_urls: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for c in citations:
            url = c.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            # 只保留必要字段，截斷 snippet
            compressed = {
                "source": c.get("source", ""),
                "title": c.get("title", ""),
                "url": url,
            }
            snippet = c.get("snippet", "")
            if snippet:
                compressed["snippet"] = snippet[:MAX_SNIPPET_LENGTH]
            # 保留 date 字段（如有）
            date = c.get("date", "")
            if date:
                compressed["date"] = date
            deduped.append(compressed)
            if len(deduped) >= MAX_CITATIONS:
                break
        if len(citations) > len(deduped):
            logger.info(
                f"[聊天] 引用壓縮: {len(citations)} → {len(deduped)} 條"
                f"（去重 + 截斷 snippet + 限量 {MAX_CITATIONS}）"
            )
        return deduped

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
        consecutive_failures = 0  # 連續失敗計數器，防止工具調用死循環
        MAX_CONSECUTIVE_FAILURES = 3  # 連續失敗上限

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
                    # 工具調用超時保護 — 單個工具最多執行 60 秒
                    try:
                        import asyncio
                        tool_result = await asyncio.wait_for(
                            self._execute_tool_call(tool_call),
                            timeout=60,
                        )
                    except asyncio.TimeoutError:
                        tool_result = ToolResult(
                            success=False,
                            content=f"工具 {tool_name} 執行超時（60秒），已跳過",
                            error="timeout",
                        )
                        logger.warning(f"[聊天工具] {tool_name} 執行超時（60秒）")
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
                    citations=self._compress_citations(all_citations),
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
            citations=self._compress_citations(all_citations),
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
        consecutive_failures = 0  # 連續失敗計數器，防止工具調用死循環
        MAX_CONSECUTIVE_FAILURES = 3  # 連續失敗上限

        # 上下文壓縮：對較早的歷史消息生成摘要，保留最近幾輪原始對話
        recent_messages, context_summary = await self._compress_context(messages)
        openai_messages = self._build_messages(recent_messages, context_summary)
        # 發送進度事件，讓用戶知道 AI 已開始處理
        yield json.dumps({
            "type": "progress",
            "text": "好的，我來為您分析一下這個問題...",
        }, ensure_ascii=False)
        tools = registry.to_openai_tools()

        tool_provider = self._get_tool_calling_provider()

        for round_idx in range(MAX_TOOL_ROUNDS):
            # 發送 thinking 事件 — 讓前端顯示「AI 思考中」動畫
            yield json.dumps({
                "type": "thinking",
                "round": round_idx + 1,
                "message": f"AI 正在思考（第 {round_idx + 1} 輪）..." if round_idx > 0 else "AI 正在分析您的問題...",
            }, ensure_ascii=False)

            try:
                # 使用真正的流式調用 — 逐 chunk 接收 LLM 輸出
                stream_provider = tool_provider
                stream_tokens = 0
                stream_content = ""
                stream_tool_calls = None

                async for event_type, event_data in self._call_llm_stream_with_fallback(
                    tool_provider, openai_messages, tools, self._get_fallback_chain(tool_provider)
                ):
                    if event_type == "content":
                        stream_content += event_data
                        yield json.dumps({"type": "content", "text": event_data}, ensure_ascii=False)
                    elif event_type == "tool_calls":
                        stream_tool_calls = event_data
                    elif event_type == "done":
                        stream_tokens = event_data.get("tokens", 0)
                        stream_provider = event_data.get("provider", tool_provider)

                if stream_tool_calls:
                    # 發送過渡性文本，讓用戶知道 AI 正在開始分析
                    yield json.dumps({
                        "type": "progress",
                        "text": "好的，我來為您分析一下這個問題...",
                    }, ensure_ascii=False)

                    # 構建 assistant message 用於後續對話
                    # 截斷 stream_content 為摘要，避免完整流式內容在 openai_messages 中累積
                    stream_content_summary = stream_content[:2000] if stream_content else None
                    assistant_msg = {
                        "role": "assistant",
                        "content": stream_content_summary,
                        "tool_calls": stream_tool_calls,
                    }
                    openai_messages.append(assistant_msg)
                    del stream_content_summary

                    for tool_call in stream_tool_calls:
                        tool_name = tool_call["function"]["name"]
                        tool_args_str = tool_call["function"]["arguments"]
                        try:
                            args = json.loads(tool_args_str)
                        except json.JSONDecodeError:
                            args = {}

                        # 智能循環保護：檢測相同工具+相同參數的重複調用失敗
                        call_sig = f"{tool_name}:{tool_args_str}"
                        if hasattr(self, '_last_fail_sig') and self._last_fail_sig == call_sig:
                            consecutive_failures += 1
                        else:
                            consecutive_failures = max(0, consecutive_failures)
                        self._last_fail_sig = call_sig

                        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                            yield json.dumps({
                                "type": "content",
                                "text": f"\n\n⚠ 工具 {tool_name} 已連續失敗 {consecutive_failures} 次，停止重試。建議換一種查詢方式或縮小查詢範圍。",
                            }, ensure_ascii=False)
                            yield json.dumps({
                                "type": "done",
                                "provider": stream_provider,
                                "model": PROVIDERS[stream_provider].model_id,
                                "citations": self._compress_citations(all_citations),
                                "tool_calls_log": all_tool_logs,
                                "tokens": stream_tokens,
                            }, ensure_ascii=False)
                            return

                        yield json.dumps({
                            "type": "tool_start",
                            "tool": tool_name,
                            "arguments": args,
                        }, ensure_ascii=False)

                        # 工具調用超時保護
                        try:
                            import asyncio
                            tool_result = await asyncio.wait_for(
                                self._execute_tool_call(tool_call),
                                timeout=60,
                            )
                        except asyncio.TimeoutError:
                            tool_result = ToolResult(
                                success=False,
                                content=f"工具 {tool_name} 執行超時（60秒），已跳過",
                                error="timeout",
                            )
                            logger.warning(f"[聊天工具] {tool_name} 執行超時（60秒）")

                        # 成功時重置失敗計數器
                        if tool_result.success:
                            consecutive_failures = 0
                            self._last_fail_sig = None

                        all_citations.extend(tool_result.citations)
                        all_tool_logs.append({
                            "tool": tool_name,
                            "arguments": tool_args_str,
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

                        # 截斷工具結果避免 openai_messages 累積大量數據
                        tool_content_truncated = tool_result.content[:20000] if tool_result.content else ""
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": tool_content_truncated,
                        })
                        del tool_content_truncated

                    continue
                else:
                    # 如果是新對話（只有一條用戶消息），生成標題
                    if len(messages) == 1 and messages[0].role == "user":
                        try:
                            title = await self._generate_title(messages[0].content)
                            yield json.dumps({
                                "type": "title_update",
                                "title": title,
                            }, ensure_ascii=False)
                        except Exception as e:
                            logger.warning(f"[標題生成] SSE 事件發送失敗: {e}")

                    # 最終回復已通過流式輸出完成，發送 done 事件
                    yield json.dumps({
                        "type": "done",
                        "provider": stream_provider,
                        "model": PROVIDERS[stream_provider].model_id,
                        "citations": self._compress_citations(all_citations),
                        "tool_calls_log": all_tool_logs,
                        "tokens": stream_tokens,
                    }, ensure_ascii=False)
                    return
            except Exception as e:
                yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
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
            "citations": self._compress_citations(all_citations),
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

    def _build_messages(self, messages: list[ChatMessage], context_summary: str | None = None) -> list[dict[str, Any]]:
        """構建 OpenAI 格式消息列表（含 system prompt）。

        安全處理：
        1. System prompt 服務端硬編碼，不接受客戶端 system role
        2. 角色白名單：只接受 user/assistant，拒絕 system/developer/tool
        3. 歷史截斷：保留最後 MAX_HISTORY_ROUNDS 輪，防止 token 耗盡
        4. 長度限制：每條消息截斷到 MAX_MESSAGE_LENGTH 字符
        5. 上下文壓縮：若提供 context_summary，注入 system prompt 中
        """
        system_content = CHAT_SYSTEM_PROMPT
        if context_summary:
            system_content += (
                "\n\n---\n【歷史對話摘要】\n"
                f"以下是之前對話的關鍵信息摘要，請參考但不要重複：\n{context_summary}"
            )
        result: list[dict[str, Any]] = [{"role": "system", "content": system_content}]

        # 安全過濾：只接受白名單角色 + 截斷超長消息
        safe_messages: list[ChatMessage] = []
        for msg in messages:
            # 角色白名單：拒絕客戶端注入的 system/developer/tool 角色
            if msg.role not in ALLOWED_CLIENT_ROLES:
                logger.warning(f"拒絕客戶端消息：非法角色 '{msg.role}'（只接受 {ALLOWED_CLIENT_ROLES}）")
                continue
            # 長度限制：截斷超長消息
            content = msg.content[:MAX_MESSAGE_LENGTH] if msg.content else ""
            safe_messages.append(ChatMessage(role=msg.role, content=content))

        # 歷史截斷：保留最後 MAX_HISTORY_ROUNDS 輪（2*N 條消息）
        max_messages = MAX_HISTORY_ROUNDS * 2
        if len(safe_messages) > max_messages:
            truncated_count = len(safe_messages) - max_messages
            safe_messages = safe_messages[-max_messages:]
            logger.info(f"歷史截斷：丟棄前 {truncated_count} 條消息，保留最後 {max_messages} 條")

        for msg in safe_messages:
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

    async def _generate_title(self, user_message: str) -> str:
        """根據用戶第一條消息生成簡潔對話標題（不超過 15 字）。"""
        title_prompt = (
            "請根據以下用戶消息生成一個簡潔的對話標題，要求：\n"
            "1. 不超過 15 個字\n"
            "2. 概括用戶的核心意圖\n"
            "3. 不要使用引號、句號等標點符號\n"
            "4. 直接輸出標題文本，不要有任何前綴說明\n\n"
            f"用戶消息：{user_message[:500]}"
        )

        try:
            summary_provider = "glm-flash"
            info = PROVIDERS[summary_provider]
            api_key = get_api_key(summary_provider)
            if not api_key:
                summary_provider = "qoder"
                info = PROVIDERS[summary_provider]
                api_key = get_api_key(summary_provider)
            if not api_key:
                return user_message[:15]

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": info.model_id,
                "messages": [{"role": "user", "content": title_prompt}],
                "temperature": 0.3,
                "max_tokens": 50,
            }
            url = f"{info.base_url}/chat/completions"

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    title = choices[0].get("message", {}).get("content", "").strip()
                    # 清理標題：去除引號、換行等
                    title = title.replace('「', '').replace('」', '').replace('"', '').replace("'", '').replace('\n', '').strip()
                    return title[:15] if title else user_message[:15]
                return user_message[:15]
        except Exception as e:
            logger.warning(f"[標題生成] 失敗: {e}，使用消息截斷")
            return user_message[:15]

    async def _summarize_history(self, messages: list[ChatMessage]) -> str:
        """用 LLM 對歷史消息生成摘要，用於上下文壓縮。"""
        # 構建對話文本
        dialog_text = ""
        for msg in messages:
            role_label = "用戶" if msg.role == "user" else "助手"
            content = msg.content[:2000] if msg.content else ""
            dialog_text += f"{role_label}: {content}\n\n"

        summary_prompt = (
            "請將以下對話歷史凝練為一段簡潔的摘要，保留關鍵信息：\n"
            "1. 用戶的核心需求和意圖\n"
            "2. 已討論的主要話題和結論\n"
            "3. 用戶提到的具體數據（股票代碼、日期、數值等）\n"
            "4. 助手提供的重要分析結果和建議\n\n"
            "要求：不超過 500 字，用條目式列出關鍵點，不要包含無關細節。\n\n"
            f"對話歷史：\n{dialog_text}"
        )

        # 使用免費供應商生成摘要（優先 glm-flash）
        summary_provider = "glm-flash"
        try:
            info = PROVIDERS[summary_provider]
            api_key = get_api_key(summary_provider)
            if not api_key:
                summary_provider = "qoder"
                info = PROVIDERS[summary_provider]
                api_key = get_api_key(summary_provider)
            if not api_key:
                # 所有免費供應商都不可用，返回簡單截斷
                return "\n".join(
                    f"{'用戶' if m.role == 'user' else '助手'}: {m.content[:100]}"
                    for m in messages
                )

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": info.model_id,
                "messages": [{"role": "user", "content": summary_prompt}],
                "temperature": 0.3,
                "max_tokens": 1024,
            }
            url = f"{info.base_url}/chat/completions"

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
                return ""
        except Exception as e:
            logger.warning(f"[上下文壓縮] 摘要生成失敗: {e}，使用簡單截斷")
            return "\n".join(
                f"{'用戶' if m.role == 'user' else '助手'}: {m.content[:100]}"
                for m in messages
            )

    async def _compress_context(self, messages: list[ChatMessage]) -> tuple[list[ChatMessage], str | None]:
        """壓縮上下文 — 將較早的歷史消息摘要化，保留最近幾輪原始對話。

        返回 (recent_messages, summary)：
          - recent_messages: 保留的最近幾輪原始消息
          - summary: 較早消息的摘要（如果未觸發壓縮則為 None）
        """
        if len(messages) <= CONTEXT_COMPRESS_THRESHOLD:
            return messages, None

        keep_count = KEEP_RECENT_ROUNDS * 2
        old_messages = messages[:-keep_count]
        recent_messages = messages[-keep_count:]

        logger.info(f"[上下文壓縮] 壓縮 {len(old_messages)} 條歷史消息，保留最近 {keep_count} 條")

        summary = await self._summarize_history(old_messages)
        if summary:
            logger.info(f"[上下文壓縮] 摘要生成成功，長度 {len(summary)} 字符")
        return recent_messages, summary

    async def _call_llm_stream_with_fallback(
        self,
        primary: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        fallback_chain: list[str],
    ) -> AsyncGenerator[tuple[str, Any], None]:
        """帶降級的流式 LLM 調用 — yield (event_type, data) 元組。

        event_type:
          - "content": data 為 str（文本片段）
          - "tool_calls": data 為 list[dict]（完整工具調用，一次性返回）
          - "done": data 為 dict（含 provider, tokens 等元信息）
        """
        last_error: Exception | None = None
        for p in fallback_chain:
            try:
                async for event in self._call_llm_stream(p, messages, tools):
                    yield event
                return
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                last_error = e
                if status in (429, 401, 403):
                    logger.warning(f"[聊天流式] 供應商 {p} 返回 {status}，降級到下一個")
                    continue
                logger.warning(f"[聊天流式] 供應商 {p} 返回 {status}，降級到下一個")
                continue
            except Exception as e:
                last_error = e
                logger.warning(f"[聊天流式] 供應商 {p} 調用失敗: {e}，降級到下一個")
                continue
        raise RuntimeError(f"所有工具調用供應商均不可用: {last_error}")

    async def _call_llm_stream(
        self,
        provider: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AsyncGenerator[tuple[str, Any], None]:
        """流式調用 LLM — 設置 stream=true，逐 chunk 解析 SSE。

        yield (event_type, data) 元組：
          - ("content", str): 文本片段
          - ("tool_calls", list[dict]): 完整工具調用列表（收集完所有 chunk 後一次性返回）
          - ("done", dict): 含 provider, model, tokens 等元信息
        """
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
            "stream": True,
        }

        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        url = f"{info.base_url}/chat/completions"
        timeout = 180 if "reasoning" in info.tags else 90

        # 流式模式下收集 tool_calls 的分塊
        collected_tool_calls: list[dict[str, Any]] = []
        collected_content = ""
        total_tokens = 0
        has_tool_calls = False

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # 提取 usage（部分供應商在最後一個 chunk 返回）
                    usage = chunk.get("usage", {})
                    if usage:
                        total_tokens = usage.get("total_tokens", 0)

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    finish_reason = choices[0].get("finish_reason")

                    # 處理文本內容
                    delta_content = delta.get("content")
                    if delta_content:
                        collected_content += delta_content
                        yield ("content", delta_content)

                    # 處理工具調用（分塊拼接）
                    delta_tool_calls = delta.get("tool_calls")
                    if delta_tool_calls:
                        has_tool_calls = True
                        for tc in delta_tool_calls:
                            idx = tc.get("index", 0)
                            # 擴展列表以容納新索引
                            while len(collected_tool_calls) <= idx:
                                collected_tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                })
                            existing = collected_tool_calls[idx]
                            if tc.get("id"):
                                existing["id"] = tc["id"]
                            func = tc.get("function", {})
                            if func.get("name"):
                                existing["function"]["name"] += func["name"]
                            if func.get("arguments"):
                                existing["function"]["arguments"] += func["arguments"]

                    # 流結束
                    if finish_reason == "tool_calls":
                        # 過濾掉空的 tool_calls
                        valid_tool_calls = [
                            tc for tc in collected_tool_calls
                            if tc.get("id") and tc.get("function", {}).get("name")
                        ]
                        if valid_tool_calls:
                            yield ("tool_calls", valid_tool_calls)
                        return

                    if finish_reason == "stop":
                        yield ("done", {
                            "provider": provider,
                            "model": info.model_id,
                            "tokens": total_tokens,
                            "content": collected_content,
                        })
                        return

        # 如果流結束但沒有明確的 finish_reason
        if has_tool_calls:
            valid_tool_calls = [
                tc for tc in collected_tool_calls
                if tc.get("id") and tc.get("function", {}).get("name")
            ]
            if valid_tool_calls:
                yield ("tool_calls", valid_tool_calls)
        else:
            yield ("done", {
                "provider": provider,
                "model": info.model_id,
                "tokens": total_tokens,
                "content": collected_content,
            })

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
