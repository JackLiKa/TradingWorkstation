"""LLM 客戶端 — 優先 Qoder SDK（免費 lite 模型），降級 Devin session API（免費 GLM-5.2 High）。

免費模型優先級：
1. Qoder lite（免費輕量化模型）— 優先
2. Devin GLM-5.2 High（免費模型）— 降級
3. 如果都不免費/不可用 → 降級關閉 AI 優化功能

統一接口: analyze(prompt) -> str (返回 LLM 的文本分析結果)
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("agent.llm")

# 免費模型清單 — 這些模型在對應平台上是免費的
# 如果平台調整了免費策略，更新這裡即可
FREE_MODELS = {
    "qoder": ["qoder-lite", "lite"],  # Qoder 免費 lite 模型
    "devin": ["glm-5.2-high", "glm-5.2", "glm5.2-high"],  # Devin 免費 GLM 模型
}


@dataclass
class ModelStatus:
    """當前可用模型狀態。"""
    provider: str = "unknown"  # "qoder" | "devin" | "none"
    model_name: str = "unknown"
    available: bool = False
    is_free: bool = False
    last_check: str = ""
    error: str = ""


class LLMClient:
    """統一 LLM 客戶端，支持 Qoder 和 Devin 雙通道降級。

    免費模型優先級：
    1. Qoder lite（免費）— 優先
    2. Devin GLM-5.2 High（免費）— 降級
    3. 都不免費/不可用 → 關閉功能
    """

    def __init__(self):
        self._model_status = ModelStatus()
        self._qoder_available = False
        self._devin_available = False
        self._devin_org_id: Optional[str] = None

    @property
    def model_status(self) -> ModelStatus:
        return self._model_status

    async def check_models(self) -> ModelStatus:
        """檢查可用的免費 LLM 提供者，更新狀態。

        邏輯：
        1. 檢查 Qoder lite（免費）是否可用
        2. 檢查 Devin GLM-5.2 High（免費）是否可用
        3. 如果都不免費/不可用 → available=False，功能關閉
        """
        # 先檢查 Qoder（免費 lite 模型）
        self._qoder_available = await self._check_qoder()
        # 再檢查 Devin（免費 GLM-5.2 High 模型）
        self._devin_available = await self._check_devin()

        if self._qoder_available:
            self._model_status = ModelStatus(
                provider="qoder",
                model_name="qoder-lite",
                available=True,
                is_free=True,
                last_check=datetime.now().isoformat(),
            )
            logger.info("使用 Qoder lite 免費模型")
        elif self._devin_available:
            self._model_status = ModelStatus(
                provider="devin",
                model_name="glm-5.2-high",
                available=True,
                is_free=True,
                last_check=datetime.now().isoformat(),
            )
            logger.info("降級使用 Devin GLM-5.2 High 免費模型")
        else:
            # 兩個平台的免費模型都不可用 → 關閉 AI 優化功能
            self._model_status = ModelStatus(
                provider="none",
                model_name="none",
                available=False,
                is_free=False,
                last_check=datetime.now().isoformat(),
                error="所有免費模型不可用，AI 優化功能已關閉",
            )
            logger.warning("所有免費模型不可用，AI 優化功能已關閉")

        logger.info(
            f"模型檢查完成: provider={self._model_status.provider}, "
            f"model={self._model_status.model_name}, "
            f"available={self._model_status.available}, "
            f"is_free={self._model_status.is_free}"
        )
        return self._model_status

    async def _check_qoder(self) -> bool:
        """檢查 Qoder SDK 是否可用（免費 lite 模型）。

        Qoder 的 lite 模型是免費的，只需要有效的 PAT。
        """
        if not settings.qoder_token:
            logger.info("Qoder PAT 未配置，跳過")
            return False
        try:
            # 嘗試導入 SDK
            from qoder_agent_sdk import QoderAgentOptions, access_token_from_env, query
            # 設置環境變量
            os.environ["QODER_PERSONAL_ACCESS_TOKEN"] = settings.qoder_token
            logger.info("Qoder lite 免費模型可用")
            return True
        except ImportError:
            logger.warning("qoder-agent-sdk 未安裝，跳過 Qoder 通道")
            return False
        except Exception as e:
            logger.warning(f"Qoder 檢查失敗: {e}")
            return False

    async def _check_devin(self) -> bool:
        """檢查 Devin API 是否可用（免費 GLM-5.2 High 模型）。

        Devin 的 GLM-5.2 High 是免費模型，需要有效的 API key。
        通過 /v3/self 端點驗證 API key 有效性。
        """
        if not settings.devin_api_key:
            logger.info("Devin API key 未配置，跳過")
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # 驗證 API key 有效性
                resp = await client.get(
                    "https://api.devin.ai/v3/self",
                    headers={"Authorization": f"Bearer {settings.devin_api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # 嘗試從 self 獲取 org_id
                    self._devin_org_id = data.get("organization_id") or data.get("org_id")
                    if not self._devin_org_id:
                        # 嘗試列出 organizations
                        resp2 = await client.get(
                            "https://api.devin.ai/v3/enterprise/organizations",
                            headers={"Authorization": f"Bearer {settings.devin_api_key}"},
                        )
                        if resp2.status_code == 200:
                            orgs = resp2.json()
                            if isinstance(orgs, list) and len(orgs) > 0:
                                self._devin_org_id = orgs[0].get("id")
                    logger.info("Devin GLM-5.2 High 免費模型可用")
                    return True
                else:
                    logger.warning(f"Devin API 認證失敗: HTTP {resp.status_code}，免費模型不可用")
                    return False
        except Exception as e:
            logger.warning(f"Devin 檢查失敗: {e}")
            return False

    async def analyze(self, prompt: str, system_prompt: str = "") -> str:
        """調用 LLM 分析，返回文本結果。

        優先 Qoder SDK（免費 lite），降級 Devin session API（免費 GLM-5.2 High）。
        如果都不免費/不可用，拋出 RuntimeError。
        """
        if not self._model_status.available:
            raise RuntimeError("沒有可用的免費 LLM 模型，AI 優化功能已關閉")

        if self._qoder_available:
            try:
                return await self._call_qoder(prompt, system_prompt)
            except Exception as e:
                logger.warning(f"Qoder 調用失敗，降級到 Devin: {e}")
                if self._devin_available:
                    return await self._call_devin(prompt, system_prompt)
                raise
        elif self._devin_available:
            return await self._call_devin(prompt, system_prompt)
        else:
            raise RuntimeError("沒有可用的免費 LLM 提供者，AI 優化功能已關閉")

    async def _call_qoder(self, prompt: str, system_prompt: str) -> str:
        """使用 Qoder SDK 調用免費 lite 模型。"""
        from qoder_agent_sdk import QoderAgentOptions, access_token_from_env, query

        os.environ["QODER_PERSONAL_ACCESS_TOKEN"] = settings.qoder_token
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        options = QoderAgentOptions(auth=access_token_from_env())
        result_text = ""

        async for message in query(prompt=full_prompt, options=options):
            # 收集文本響應
            if hasattr(message, "content"):
                for block in message.content if isinstance(message.content, list) else [message.content]:
                    if hasattr(block, "text"):
                        result_text += block.text
            elif isinstance(message, str):
                result_text += message

        return result_text.strip()

    async def _call_devin(self, prompt: str, system_prompt: str) -> str:
        """使用 Devin session API 調用免費 GLM-5.2 High 模型。"""
        if not self._devin_org_id:
            await self._check_devin()
        if not self._devin_org_id:
            raise RuntimeError("無法獲取 Devin org_id，免費模型不可用")

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        async with httpx.AsyncClient(timeout=120) as client:
            # 創建會話
            resp = await client.post(
                f"https://api.devin.ai/v3/organizations/{self._devin_org_id}/sessions",
                headers={
                    "Authorization": f"Bearer {settings.devin_api_key}",
                    "Content-Type": "application/json",
                },
                json={"prompt": full_prompt},
            )
            resp.raise_for_status()
            session_data = resp.json()
            session_id = session_data.get("devin_id") or session_data.get("session_id")

            if not session_id:
                raise RuntimeError("Devin 會話創建失敗：未返回 session_id")

            # 輪詢會話狀態直到完成
            import asyncio
            for _ in range(60):  # 最多等待 5 分鐘
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"https://api.devin.ai/v3/organizations/{self._devin_org_id}/sessions/{session_id}",
                    headers={"Authorization": f"Bearer {settings.devin_api_key}"},
                )
                status_resp.raise_for_status()
                status_data = status_resp.json()
                state = status_data.get("state", "")
                if state == "completed":
                    # 獲取消息
                    msg_resp = await client.get(
                        f"https://api.devin.ai/v3/organizations/{self._devin_org_id}/sessions/{session_id}/messages",
                        headers={"Authorization": f"Bearer {settings.devin_api_key}"},
                    )
                    msg_resp.raise_for_status()
                    messages = msg_resp.json()
                    # 提取 assistant 消息
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

            raise RuntimeError("Devin 會話超時")


# 全局 LLM 客戶端
llm_client = LLMClient()
