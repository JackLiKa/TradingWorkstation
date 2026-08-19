"""後端 API 客戶端 — 調用量化交易後端的 screener 和 backtest REST API。

工程化改進：
- 共享 httpx.AsyncClient 連接池（避免每次調用創建新連接）
- 指數退避重試（對 5xx 和網絡錯誤自動重試 3 次）
- 統一超時管理
- 請求/響應日誌（DEBUG 級別）
"""
import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core import rate_limiter
from app.core.metrics import record_backend_call

logger = logging.getLogger("agent.backend")

# 重試配置
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # 基礎延遲（秒），指數退避: 1s, 2s, 4s


class BackendClient:
    """調用後端 REST API 的異步客戶端。

    封裝對量化交易後端（Java Spring Boot，默認 localhost:8090）的
    screener / backtest / dashboard / stock 等接口的調用。

    使用共享連接池 + 指數退避重試，提高可靠性。
    """

    def __init__(self):
        self._base_url = settings.backend_api_url
        # 共享連接池（限制 20 並發連接，復用 TCP 連接）
        self._client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            timeout=httpx.Timeout(600.0, connect=10.0),
        )

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        json_data: dict = None,
        params: dict = None,
        timeout: float = None,
    ) -> dict[str, Any]:
        """帶速率限制 + 指數退避重試的 HTTP 請求。

        對 5xx 錯誤和網絡錯誤自動重試，4xx 錯誤不重試。
        調用前先通過速率限制器（防止壓垮後端）。
        """
        # 提取端點路徑（用於速率限制分組）
        endpoint = url.replace(self._base_url, "").split("?")[0]

        last_error = None
        was_retried = False
        for attempt in range(1, MAX_RETRIES + 1):
            # 速率限制（每次調用前都檢查，包括重試）
            allowed = await rate_limiter.acquire(endpoint, timeout=120.0)
            if not allowed:
                record_backend_call(endpoint, success=False, retried=False)
                raise RuntimeError(f"速率限制等待超時: {endpoint}")

            try:
                req_timeout = timeout or 600
                if method == "GET":
                    resp = await self._client.get(
                        url, params=params, timeout=req_timeout,
                    )
                else:
                    resp = await self._client.post(
                        url, json=json_data, timeout=req_timeout,
                    )

                # 5xx 錯誤重試
                if resp.status_code >= 500:
                    was_retried = True
                    last_error = httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                    if attempt < MAX_RETRIES:
                        delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                        logger.warning(f"後端返回 {resp.status_code}，{delay}s 後重試 (attempt {attempt}/{MAX_RETRIES})")
                        await asyncio.sleep(delay)
                        continue
                    record_backend_call(endpoint, success=False, retried=was_retried)
                    resp.raise_for_status()

                resp.raise_for_status()
                record_backend_call(endpoint, success=True, retried=was_retried)
                return resp.json()

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as e:
                was_retried = True
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(f"後端連接失敗: {e}，{delay}s 後重試 (attempt {attempt}/{MAX_RETRIES})")
                    await asyncio.sleep(delay)
                    continue
                record_backend_call(endpoint, success=False, retried=was_retried)
                raise
            except httpx.HTTPStatusError:
                record_backend_call(endpoint, success=False, retried=was_retried)
                raise  # 4xx 不重試
            except Exception as e:
                was_retried = True
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(f"後端請求異常: {e}，{delay}s 後重試 (attempt {attempt}/{MAX_RETRIES})")
                    await asyncio.sleep(delay)
                    continue
                record_backend_call(endpoint, success=False, retried=was_retried)
                raise

        record_backend_call(endpoint, success=False, retried=was_retried)
        raise last_error or RuntimeError("後端請求失敗（重試耗盡）")

    async def aclose(self):
        """關閉連接池（應用關閉時調用）。"""
        await self._client.aclose()

    async def run_screener(self, criteria: dict[str, Any]) -> dict[str, Any]:
        """運行選股，返回篩選結果。"""
        data = await self._request_with_retry(
            "POST", f"{self._base_url}/api/screener/run",
            json_data=criteria, timeout=600,
        )
        if not data.get("success"):
            raise RuntimeError(f"選股失敗: {data.get('message')}")
        return data["data"]

    async def run_backtest(self, criteria: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        """運行回測，返回回測結果。"""
        data = await self._request_with_retry(
            "POST", f"{self._base_url}/api/backtest/run",
            json_data={"criteria": criteria, "config": config}, timeout=600,
        )
        if not data.get("success"):
            raise RuntimeError(f"回測失敗: {data.get('message')}")
        return data["data"]

    async def save_strategy(self, name: str, criteria: dict, config: dict, result: dict) -> dict:
        """保存策略到後端數據庫。"""
        data = await self._request_with_retry(
            "POST", f"{self._base_url}/api/backtest/strategies",
            json_data={"name": name, "criteria": criteria, "config": config, "result": result},
            timeout=30,
        )
        return data.get("data", {})

    async def list_strategies(self) -> list[dict[str, Any]]:
        """獲取已保存的策略列表。後端不可用時返回空列表。"""
        try:
            data = await self._request_with_retry(
                "GET", f"{self._base_url}/api/backtest/strategies", timeout=15,
            )
            if not data.get("success"):
                return []
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"獲取策略列表失敗: {e}")
            return []

    async def get_strategy(self, strategy_id: int) -> dict[str, Any]:
        """獲取單個策略詳情。"""
        data = await self._request_with_retry(
            "GET", f"{self._base_url}/api/backtest/strategies/{strategy_id}", timeout=15,
        )
        return data.get("data", {})

    async def get_market_overview(self) -> dict[str, Any]:
        """獲取市場概覽（dashboard summary）。"""
        data = await self._request_with_retry(
            "GET", f"{self._base_url}/api/dashboard/summary", timeout=15,
        )
        return data.get("data", {})

    async def get_industries(self, code: str = None, industry: str = None) -> list[dict[str, Any]]:
        """查詢股票行業分類數據。"""
        params = {}
        if code:
            params["code"] = code
        if industry:
            params["industry"] = industry
        try:
            data = await self._request_with_retry(
                "GET", f"{self._base_url}/api/stock/industries",
                params=params, timeout=15,
            )
            if not data.get("success"):
                return []
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"查詢行業失敗: {e}")
            return []

    async def get_industry_list(self) -> list[str]:
        """獲取所有不同行業名稱列表。"""
        try:
            data = await self._request_with_retry(
                "GET", f"{self._base_url}/api/stock/industries/list", timeout=15,
            )
            if not data.get("success"):
                return []
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"獲取行業列表失敗: {e}")
            return []

    async def health(self) -> bool:
        """檢查後端是否可用（帶超時，不重試）。"""
        try:
            resp = await self._client.get(
                f"{self._base_url}/api/system/health", timeout=5.0,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"後端健康檢查失敗: {e}")
            return False

    async def log_ai_call(
        self,
        iteration: int,
        stage_name: str,
        stage_display_name: str,
        provider: str,
        model_name: str,
        input_json: str,
        output_text: str,
        output_json: str,
        judge_score: float,
        judge_passed: bool,
        judge_feedback: str,
        attempts: int,
        duration_ms: int,
        error: str = None,
    ) -> dict:
        """記錄一條 AI 調用日誌到後端 ai_call_log 表。

        後端不可用時靜默失敗，不影響優化循環。
        """
        try:
            data = await self._request_with_retry(
                "POST", f"{self._base_url}/api/aicalllog/log",
                json_data={
                    "iteration": iteration,
                    "stageName": stage_name,
                    "stageDisplayName": stage_display_name,
                    "provider": provider,
                    "modelName": model_name,
                    "inputJson": input_json,
                    "outputText": output_text,
                    "outputJson": output_json,
                    "judgeScore": judge_score,
                    "judgePassed": judge_passed,
                    "judgeFeedback": judge_feedback,
                    "attempts": attempts,
                    "durationMs": duration_ms,
                    "error": error,
                },
                timeout=10,
            )
            return data.get("data", {})
        except Exception as e:
            logger.warning(f"寫入 ai_call_log 失敗（不影響優化）: {e}")
            return {}


# 全局後端客戶端單例
backend_client = BackendClient()
