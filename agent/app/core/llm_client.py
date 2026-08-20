"""LLM 客戶端 — 多模型路由架構 + 自動降級 + 全鏈路可觀測。

支持供應商（2026 性價比優先）：
1. DeepSeek V4-Pro / V4-Flash（OpenAI-compatible, 推理最強 + 性價比）
2. GLM-5.2 / GLM-4-Flash（OpenAI-compatible, JSON 最穩定 + 免費 Flash）
3. Qwen3.6（OpenAI-compatible, 中文金融最佳）
4. Qoder Lite（agent SDK, 免費備用）
5. Devin GLM-5.2-High（agent session, 免費備用, 延遲高）

統一接口: analyze(prompt, system_prompt, preferred_provider, json_mode) -> LLMResponse

路由邏輯：
- 每個階段有默認供應商（見 providers.STAGE_DEFAULT_PROVIDERS）
- 用戶可通過 API/前端覆蓋每個階段的供應商
- preferred_provider 參數可臨時指定供應商
- 主供應商失敗時自動降級到備用供應商
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.core.metrics import record_llm_call
from app.core.providers import (
    PROVIDERS,
    get_api_key,
    is_openai_compatible,
)

logger = logging.getLogger("agent.llm")


@dataclass
class LLMResponse:
    """LLM 調用結果 — 包含文本輸出和可觀測性元數據。"""

    text: str
    provider: str
    model_name: str
    duration_ms: int
    fallback_from: str = ""
    error: str = ""


@dataclass
class ModelStatus:
    """當前可用模型狀態。"""

    provider: str = "unknown"
    model_name: str = "unknown"
    available: bool = False
    is_free: bool = False
    last_check: str = ""
    error: str = ""


class LLMClient:
    """統一 LLM 客戶端 — 多模型路由 + 自動降級 + 可觀測。

    供應商優先級（可被 preferred_provider / stage_providers 覆蓋）：
    1. 用戶指定供應商 → 嘗試該供應商
    2. 階段默認供應商 → 嘗試該供應商
    3. 自動選擇 → 按可用性 + 性價比排序
    4. 降級鏈: deepseek-flash → glm-flash → qoder → devin
    """

    def __init__(self):
        self._model_status = ModelStatus()
        self._provider_status: dict[str, bool] = {}  # provider_id -> available
        self._devin_org_id: str | None = None

    @property
    def model_status(self) -> ModelStatus:
        return self._model_status

    async def check_models(self) -> ModelStatus:
        """檢查所有供應商的可用性，更新狀態。"""
        self._provider_status = {}

        for provider_id, info in PROVIDERS.items():
            available = await self._check_provider(provider_id)
            self._provider_status[provider_id] = available
            if available:
                logger.info(f"供應商可用: {info.display_name} ({provider_id})")
            else:
                logger.debug(f"供應商不可用: {info.display_name} ({provider_id})")

        # 選擇最佳可用供應商作為默認狀態
        best = self._select_best_provider()
        if best:
            info = PROVIDERS[best]
            self._model_status = ModelStatus(
                provider=best,
                model_name=info.model_id,
                available=True,
                is_free=info.is_free,
                last_check=datetime.now().isoformat(),
            )
            logger.info(f"默認供應商: {info.display_name}")
        else:
            self._model_status = ModelStatus(
                provider="none",
                model_name="none",
                available=False,
                is_free=False,
                last_check=datetime.now().isoformat(),
                error="所有供應商不可用",
            )
            logger.warning("所有供應商不可用")

        return self._model_status

    def _select_best_provider(self) -> str:
        """選擇最佳可用供應商（優先免費 + OpenAI-compatible）。"""
        # 優先級：免費的 OpenAI-compatible > 付費的 OpenAI-compatible > agent SDK
        priority_order = [
            "glm-flash",  # 免費 + JSON 穩定
            "deepseek-flash",  # 便宜 + 快
            "qwen",  # 中文最佳
            "glm-5.2",  # JSON 最穩定
            "deepseek-pro",  # 推理最強
            "qoder",  # 免費 SDK
            "devin",  # 免費 session（延遲高）
        ]
        for pid in priority_order:
            if self._provider_status.get(pid):
                return pid
        return ""

    async def _check_provider(self, provider_id: str) -> bool:
        """檢查單個供應商是否可用。"""
        info = PROVIDERS.get(provider_id)
        if not info:
            return False

        # 檢查 API key
        api_key = get_api_key(provider_id)
        if not api_key:
            return False

        # Qoder 需要 SDK
        if provider_id == "qoder":
            try:
                from qoder_agent_sdk import QoderAgentOptions  # noqa: F401

                os.environ["QODER_PERSONAL_ACCESS_TOKEN"] = api_key
                return True
            except ImportError:
                return False

        # Devin 需要 API 可達
        if provider_id == "devin":
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        "https://api.devin.ai/v3/self",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        self._devin_org_id = data.get("organization_id") or data.get("org_id")
                        if not self._devin_org_id:
                            resp2 = await client.get(
                                "https://api.devin.ai/v3/enterprise/organizations",
                                headers={"Authorization": f"Bearer {api_key}"},
                            )
                            if resp2.status_code == 200:
                                orgs = resp2.json()
                                if isinstance(orgs, list) and len(orgs) > 0:
                                    self._devin_org_id = orgs[0].get("id")
                        return True
                    return False
            except Exception:
                return False

        # OpenAI-compatible 供應商：有 API key 即視為可用
        if is_openai_compatible(provider_id):
            return True

        return False

    def get_available_providers(self) -> list[dict]:
        """返回當前可用的供應商列表（供前端選擇）。"""
        providers = []
        for pid, info in PROVIDERS.items():
            available = self._provider_status.get(pid, False)
            providers.append(
                {
                    "provider": pid,
                    "display_name": info.display_name,
                    "model": info.model_id,
                    "available": available,
                    "is_free": info.is_free,
                }
            )
        # 按可用性 + 免費優先排序
        providers.sort(key=lambda p: (not p["available"], not p["is_free"]))
        return providers

    def get_all_model_statuses(self) -> list[dict]:
        """返回所有供應商的詳細檢查狀態（供前端展示全部模型）。"""
        last_check = self._model_status.last_check
        result = []
        for pid, info in PROVIDERS.items():
            available = self._provider_status.get(pid, False)
            api_key_set = bool(get_api_key(pid))
            error = ""
            if not available:
                if not api_key_set:
                    error = f"未配置 {info.api_key_env}"
                elif pid == "qoder":
                    error = "qoder-agent-sdk 未安裝"
                elif pid == "devin":
                    error = "Devin API 不可達"
                else:
                    error = "API key 已配置但檢查失敗"
            result.append(
                {
                    "provider": pid,
                    "display_name": info.display_name,
                    "model_name": info.model_id,
                    "available": available,
                    "is_free": info.is_free,
                    "last_check": last_check,
                    "error": error,
                    "supports_json_mode": info.supports_json_mode,
                    "tags": info.tags,
                }
            )
        return result

    def get_fallback_chain(self, preferred: str = "") -> list[str]:
        """獲取降級鏈（主供應商 + 備用供應商列表）。"""
        chain = []
        if preferred and self._provider_status.get(preferred):
            chain.append(preferred)

        # 降級順序（排除已在 chain 中的）
        fallback_order = [
            "glm-flash",
            "deepseek-flash",
            "qwen",
            "glm-5.2",
            "deepseek-pro",
            "qoder",
            "devin",
        ]
        for pid in fallback_order:
            if pid not in chain and self._provider_status.get(pid):
                chain.append(pid)
        return chain

    async def analyze(
        self,
        prompt: str,
        system_prompt: str = "",
        preferred_provider: str = "",
        json_mode: bool = False,
    ) -> LLMResponse:
        """調用 LLM 分析，返回 LLMResponse（含可觀測性元數據）。

        Args:
            prompt: 用戶提示詞
            system_prompt: 系統提示詞
            preferred_provider: 手動指定供應商 ID（如 "deepseek-pro"）
            json_mode: 是否啟用 JSON 結構化輸出模式

        路由邏輯：
        1. preferred_provider 指定 → 用該供應商
        2. 否則用階段默認供應商（調用方應傳入）
        3. 失敗時自動降級到備用供應商
        """
        # 自動觸發模型檢查
        if not self._model_status.available:
            logger.info("模型狀態不可用，自動觸發模型檢查...")
            await self.check_models()
        if not self._model_status.available:
            raise RuntimeError("沒有可用的 LLM 供應商（已嘗試自動檢查）")

        # 構建降級鏈
        chain = self.get_fallback_chain(preferred_provider)
        if not chain:
            raise RuntimeError("沒有可用的 LLM 供應商")

        start = time.time()
        last_error = None

        for i, provider_id in enumerate(chain):
            info = PROVIDERS[provider_id]
            try:
                text = await self._call_provider(provider_id, prompt, system_prompt, json_mode)
                duration_s = time.time() - start
                duration_ms = int(duration_s * 1000)
                fallback_from = chain[0] if i > 0 else ""

                # 記錄指標
                record_llm_call(
                    provider=provider_id,
                    model=info.model_id,
                    duration_s=duration_s,
                    fallback=bool(fallback_from),
                )

                return LLMResponse(
                    text=text,
                    provider=provider_id,
                    model_name=info.model_id,
                    duration_ms=duration_ms,
                    fallback_from=fallback_from,
                )
            except Exception as e:
                last_error = e
                logger.warning(f"供應商 {info.display_name} 調用失敗: {e}")
                if i < len(chain) - 1:
                    logger.info(f"降級到: {PROVIDERS[chain[i + 1]].display_name}")
                continue

        duration_ms = int((time.time() - start) * 1000)
        raise RuntimeError(f"所有供應商調用失敗: {last_error}")

    async def _call_provider(
        self,
        provider_id: str,
        prompt: str,
        system_prompt: str,
        json_mode: bool = False,
    ) -> str:
        """調用指定供應商（統一入口，內部路由到 OpenAI API / Qoder SDK / Devin session）。"""
        info = PROVIDERS[provider_id]
        api_key = get_api_key(provider_id)

        if not api_key:
            raise RuntimeError(f"{info.display_name} API key 未配置")

        if provider_id == "qoder":
            return await self._call_qoder(prompt, system_prompt, api_key)
        elif provider_id == "devin":
            return await self._call_devin(prompt, system_prompt, api_key)
        elif is_openai_compatible(provider_id):
            return await self._call_openai_compatible(
                info,
                api_key,
                prompt,
                system_prompt,
                json_mode,
            )
        else:
            raise RuntimeError(f"未知供應商類型: {provider_id}")

    async def _call_openai_compatible(
        self,
        info,
        api_key: str,
        prompt: str,
        system_prompt: str,
        json_mode: bool = False,
    ) -> str:
        """調用 OpenAI-compatible API（DeepSeek/GLM/Qwen 統一接口）。"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body: dict = {
            "model": info.model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        # JSON 結構化輸出模式
        if json_mode and info.supports_json_mode:
            body["response_format"] = {"type": "json_object"}

        url = f"{info.base_url}/chat/completions"
        timeout = 120 if "pro" in info.provider else 60

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError(f"{info.display_name} 返回空 choices")
            return choices[0]["message"]["content"].strip()

    async def _call_qoder(self, prompt: str, system_prompt: str, api_key: str) -> str:
        """調用 Qoder agent SDK。"""
        from qoder_agent_sdk import QoderAgentOptions, access_token_from_env, query

        os.environ["QODER_PERSONAL_ACCESS_TOKEN"] = api_key
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        options = QoderAgentOptions(auth=access_token_from_env())
        result_text = ""
        async for message in query(prompt=full_prompt, options=options):
            if hasattr(message, "content"):
                for block in message.content if isinstance(message.content, list) else [message.content]:
                    if hasattr(block, "text"):
                        result_text += block.text
            elif isinstance(message, str):
                result_text += message
        return result_text.strip()

    async def _call_devin(self, prompt: str, system_prompt: str, api_key: str) -> str:
        """調用 Devin agent session API（延遲較高，備用）。"""
        if not self._devin_org_id:
            await self._check_provider("devin")
        if not self._devin_org_id:
            raise RuntimeError("無法獲取 Devin org_id")

        max_prompt_chars = 4000
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        if len(full_prompt) > max_prompt_chars:
            full_prompt = full_prompt[:max_prompt_chars] + "\n\n[輸入已截斷]"

        max_polls = 24
        poll_interval = 3
        import asyncio

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.devin.ai/v3/organizations/{self._devin_org_id}/sessions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"prompt": full_prompt},
            )
            resp.raise_for_status()
            session_data = resp.json()
            session_id = session_data.get("devin_id") or session_data.get("session_id")
            if not session_id:
                raise RuntimeError("Devin 會話創建失敗")
            for _poll in range(max_polls):
                await asyncio.sleep(poll_interval)
                status_resp = await client.get(
                    f"https://api.devin.ai/v3/organizations/{self._devin_org_id}/sessions/{session_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                status_resp.raise_for_status()
                status_data = status_resp.json()
                state = status_data.get("state", "")
                if state == "completed":
                    msg_resp = await client.get(
                        f"https://api.devin.ai/v3/organizations/{self._devin_org_id}/sessions/{session_id}/messages",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    msg_resp.raise_for_status()
                    messages = msg_resp.json()
                    result = ""
                    for msg in messages if isinstance(messages, list) else messages.get("messages", []):
                        if msg.get("role") == "assistant":
                            content = msg.get("content", "")
                            if isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        result += block.get("text", "")
                            elif isinstance(content, str):
                                result += content
                    return result.strip()
                elif state in ("failed", "cancelled", "archived"):
                    raise RuntimeError(f"Devin 會話結束: state={state}")
            raise RuntimeError(f"Devin 會話超時（{max_polls * poll_interval}s）")


llm_client = LLMClient()
