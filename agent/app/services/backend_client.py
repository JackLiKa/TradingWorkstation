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

from app.core import rate_limiter
from app.core.config import settings
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
                        url,
                        params=params,
                        timeout=req_timeout,
                    )
                else:
                    resp = await self._client.post(
                        url,
                        json=json_data,
                        timeout=req_timeout,
                    )

                # 5xx 錯誤重試
                if resp.status_code >= 500:
                    was_retried = True
                    last_error = httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
                    if attempt < MAX_RETRIES:
                        delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                        logger.warning(
                            f"後端返回 {resp.status_code}，{delay}s 後重試 (attempt {attempt}/{MAX_RETRIES})"
                        )
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
            "POST",
            f"{self._base_url}/api/screener/run",
            json_data=criteria,
            timeout=600,
        )
        if not data.get("success"):
            raise RuntimeError(f"選股失敗: {data.get('message')}")
        return data["data"]

    async def run_backtest(self, criteria: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        """運行回測，返回回測結果。"""
        data = await self._request_with_retry(
            "POST",
            f"{self._base_url}/api/backtest/run",
            json_data={"criteria": criteria, "config": config},
            timeout=600,
        )
        if not data.get("success"):
            raise RuntimeError(f"回測失敗: {data.get('message')}")
        return data["data"]

    async def save_strategy(self, name: str, criteria: dict, config: dict, result: dict) -> dict:
        """保存策略到後端數據庫。"""
        data = await self._request_with_retry(
            "POST",
            f"{self._base_url}/api/backtest/strategies",
            json_data={"name": name, "criteria": criteria, "config": config, "result": result},
            timeout=30,
        )
        return data.get("data", {})

    async def list_strategies(self) -> list[dict[str, Any]]:
        """獲取已保存的策略列表。後端不可用時返回空列表。"""
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/backtest/strategies",
                timeout=15,
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
            "GET",
            f"{self._base_url}/api/backtest/strategies/{strategy_id}",
            timeout=15,
        )
        return data.get("data", {})

    async def get_market_overview(self) -> dict[str, Any]:
        """獲取市場概覽（dashboard summary）。"""
        data = await self._request_with_retry(
            "GET",
            f"{self._base_url}/api/dashboard/summary",
            timeout=15,
        )
        return data.get("data", {})

    async def get_index_history(self, code: str, days: int = 10) -> list[dict[str, Any]]:
        """獲取指數最近 N 日的歷史數據（用於市場形態識別）。

        Args:
            code: 指數代碼（如 sh000001）
            days: 最近天數（默認 10）

        Returns:
            list[dict]: 指數日線列表，每項含 code/tradeDate/closePrice/pctChange
        """
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/index-history",
                params={"code": code, "days": days},
                timeout=15,
            )
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"獲取指數歷史失敗 (code={code}): {e}")
            return []

    async def get_sector_performance(self, days: int = 10) -> list[dict[str, Any]]:
        """獲取最近 N 個交易日的板塊表現（各行業平均漲跌幅 + 領漲股）。

        Args:
            days: 最近交易日天數（默認 10）

        Returns:
            list[dict]: 板塊表現列表，每項含 date/industry/avgPctChange/topCode/topCodeName/topPctChange
        """
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/sector-performance",
                params={"days": days},
                timeout=20,
            )
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"獲取板塊表現失敗: {e}")
            return []

    async def get_index_list(self, category_code: str | None = None) -> list[dict[str, Any]]:
        """獲取指數元數據列表（代碼/名稱/分類）。

        數據來源：ingestion/index_list.json → index_metadata 表。
        共 10 大類別 ~80 個指數（綜合/規模/一級行業/二級行業/策略/成長/價值/主題/基金/債券）。

        Args:
            category_code: 可選，按分類英文代碼過濾
                (composite/scale/industry_l1/industry_l2/strategy/growth/value/theme/fund/bond)

        Returns:
            list[dict]: 指數元數據列表，每項含 code/name/category/categoryCode
        """
        try:
            params = {"categoryCode": category_code} if category_code else {}
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/index-list",
                params=params,
                timeout=15,
            )
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"獲取指數元數據列表失敗: {e}")
            return []

    async def get_index_history_batch(self, codes: list[str], days: int = 10) -> dict[str, list[dict[str, Any]]]:
        """批量獲取多個指數最近 N 日的歷史數據（一次後端調用）。

        用於 AI 多維市場分析，減少多次單指數 API 調用的開銷。

        Args:
            codes: 指數代碼列表（如 ["sh.000001", "sz.399001", "sh.000300"])
            days: 最近天數（默認 10）

        Returns:
            dict[str, list[dict]]: 按指數代碼分組的歷史數據
        """
        if not codes:
            return {}
        try:
            data = await self._request_with_retry(
                "POST",
                f"{self._base_url}/api/stock/index-history/batch",
                json_data={"codes": codes, "days": days},
                timeout=30,
            )
            return data.get("data", {})
        except Exception as e:
            logger.warning(f"批量獲取指數歷史失敗: {e}")
            return {}

    async def get_market_breadth(self, days: int = 10) -> dict[str, Any]:
        """獲取市場廣度分析（綜合/規模/風格/行業）。

        基於 index_metadata 中 10 大類別 ~80 個指數計算。

        Args:
            days: 最近交易日天數（默認 10）

        Returns:
            dict: 市場廣度 DTO，含 compositeBreadth/scaleBreadth/styleBreadth/leading/lagging/summary
        """
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/market-breadth",
                params={"days": days},
                timeout=30,
            )
            return data.get("data", {})
        except Exception as e:
            logger.warning(f"獲取市場廣度失敗: {e}")
            return {}

    async def get_rotation_signals(self, days: int = 10) -> dict[str, Any]:
        """獲取輪動信號分析（行業與風格輪動）。

        基於一級/二級行業指數和成長/價值指數計算。

        Args:
            days: 最近交易日天數（默認 10）

        Returns:
            dict: 輪動信號 DTO，含 industryRotation/styleRotation/leading/lagging/rotationStrength/summary
        """
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/rotation",
                params={"days": days},
                timeout=30,
            )
            return data.get("data", {})
        except Exception as e:
            logger.warning(f"獲取輪動信號失敗: {e}")
            return {}

    async def get_latest_trade_date(self) -> str | None:
        """獲取數據庫中已有數據的最新交易日。

        用於校準 AI 策略優化的基準日期，避免使用未來日期或缺失數據的日期。
        後端 /api/dashboard/summary 返回 latestTradeDate 字段。

        Returns:
            str | None: 最新交易日字符串（YYYY-MM-DD），後端不可用時返回 None
        """
        try:
            data = await self.get_market_overview()
            latest = data.get("latestTradeDate")
            if latest:
                return str(latest)[:10]  # 確保 YYYY-MM-DD 格式
            return None
        except Exception as e:
            logger.warning(f"獲取最新交易日失敗: {e}")
            return None

    async def get_data_range(self) -> tuple[str | None, str | None]:
        """獲取數據庫中已有數據的最早和最新交易日。

        用於校驗用戶手動指定的回測日期區間是否在數據庫覆蓋範圍內。
        後端 /api/dashboard/summary 返回 earliestTradeDate 和 latestTradeDate 字段。

        Returns:
            tuple[str | None, str | None]: (最早交易日, 最新交易日)，後端不可用時返回 (None, None)
        """
        try:
            data = await self.get_market_overview()
            earliest = data.get("earliestTradeDate")
            latest = data.get("latestTradeDate")
            earliest_str = str(earliest)[:10] if earliest else None
            latest_str = str(latest)[:10] if latest else None
            return earliest_str, latest_str
        except Exception as e:
            logger.warning(f"獲取數據範圍失敗: {e}")
            return None, None

    async def get_industry_daily(self, trade_date: str = None) -> list[dict[str, Any]]:
        """獲取指定交易日的行業日聚合數據。

        數據來自 industry_daily 表，含行業平均漲跌幅、成交、漲跌家數等。

        Args:
            trade_date: 交易日期 YYYY-MM-DD，為空時使用最新交易日

        Returns:
            list[dict]: 行業聚合列表
        """
        params = {}
        if trade_date:
            params["tradeDate"] = trade_date
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/industry-daily",
                params=params,
                timeout=15,
            )
            if not data.get("success"):
                return []
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"獲取行業日聚合失敗: {e}")
            return []

    async def get_industry_daily_range(self, industry: str, start: str, end: str) -> list[dict[str, Any]]:
        """獲取指定行業在日期區間內的日聚合數據。

        Args:
            industry: 行業名稱
            start: 起始日期 YYYY-MM-DD
            end: 結束日期 YYYY-MM-DD

        Returns:
            list[dict]: 行業聚合序列
        """
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/industry-daily/range",
                params={"industry": industry, "start": start, "end": end},
                timeout=15,
            )
            if not data.get("success"):
                return []
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"獲取行業區間聚合失敗: {e}")
            return []

    async def get_all_industry_daily_range(self, start: str, end: str) -> list[dict[str, Any]]:
        """獲取日期區間內全部行業的日聚合數據（用於相關性矩陣計算）。

        Args:
            start: 起始日期 YYYY-MM-DD
            end: 結束日期 YYYY-MM-DD

        Returns:
            list[dict]: 全部行業聚合序列（按日期升序、行業升序）
        """
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/industry-daily/all-range",
                params={"start": start, "end": end},
                timeout=20,
            )
            if not data.get("success"):
                return []
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"獲取全部行業區間聚合失敗: {e}")
            return []

    async def get_industry_prosperity(self, trade_date: str = None) -> list[dict[str, Any]]:
        """獲取行業景氣度指標（綜合評分）。

        Args:
            trade_date: 交易日期 YYYY-MM-DD，為空時取最新交易日

        Returns:
            list[dict]: 行業景氣度列表（按 prosperityIndex 倒序）
        """
        try:
            params = {}
            if trade_date:
                params["tradeDate"] = trade_date
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/industry-prosperity",
                params=params,
                timeout=15,
            )
            if not data.get("success"):
                return []
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"獲取行業景氣度失敗: {e}")
            return []

    async def get_rotation_prediction(self, lookback_days: int = 20) -> dict[str, Any]:
        """獲取行業輪動預測結果。

        Args:
            lookback_days: 回溯天數（默認 20）

        Returns:
            dict: 輪動預測 DTO（含 predictedLeaders, predictedLaggards, confidence 等）
        """
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/rotation-prediction",
                params={"lookbackDays": lookback_days},
                timeout=15,
            )
            if not data.get("success"):
                return {}
            return data.get("data", {})
        except Exception as e:
            logger.warning(f"獲取輪動預測失敗: {e}")
            return {}

    async def get_industries(self, code: str = None, industry: str = None) -> list[dict[str, Any]]:
        """查詢股票行業分類數據。"""
        params = {}
        if code:
            params["code"] = code
        if industry:
            params["industry"] = industry
        try:
            data = await self._request_with_retry(
                "GET",
                f"{self._base_url}/api/stock/industries",
                params=params,
                timeout=15,
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
                "GET",
                f"{self._base_url}/api/stock/industries/list",
                timeout=15,
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
                f"{self._base_url}/api/system/health",
                timeout=5.0,
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
                "POST",
                f"{self._base_url}/api/aicalllog/log",
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
