"""後端 API 客戶端 — 調用量化交易後端的 screener 和 backtest REST API。"""
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("agent.backend")


class BackendClient:
    """調用後端 REST API 的異步客戶端。

    封裝對量化交易後端（Java Spring Boot，默認 localhost:8090）的
    screener / backtest / dashboard / stock 等接口的調用。
    """

    def __init__(self):
        self._base_url = settings.backend_api_url

    async def run_screener(self, criteria: dict[str, Any]) -> dict[str, Any]:
        """運行選股，返回篩選結果。

        Args:
            criteria: 選股條件字典（如 asOfDate、adjustflag、minClose 等）

        Returns:
            dict: 篩選結果數據（命中股票列表）

        Raises:
            RuntimeError: 後端返回 success=false 時拋出
        """
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(
                f"{self._base_url}/api/screener/run",
                json=criteria,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(f"選股失敗: {data.get('message')}")
            return data["data"]

    async def run_backtest(self, criteria: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        """運行回測，返回回測結果。

        Args:
            criteria: 選股條件字典
            config: 回測配置字典（如 startDate、rebalanceInterval 等）

        Returns:
            dict: 回測結果，包含 statistics（統計指標）和 logLines（日誌）

        Raises:
            RuntimeError: 後端返回 success=false 時拋出
        """
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(
                f"{self._base_url}/api/backtest/run",
                json={"criteria": criteria, "config": config},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(f"回測失敗: {data.get('message')}")
            return data["data"]

    async def save_strategy(self, name: str, criteria: dict, config: dict, result: dict) -> dict:
        """保存策略到後端數據庫。

        Args:
            name: 策略名稱
            criteria: 選股條件
            config: 回測配置
            result: 回測結果（含統計指標）

        Returns:
            dict: 保存後的策略記錄（含後端生成的 id）
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base_url}/api/backtest/strategies",
                json={"name": name, "criteria": criteria, "config": config, "result": result},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {})

    async def list_strategies(self) -> list[dict[str, Any]]:
        """獲取已保存的策略列表。

        Returns:
            list[dict]: 策略摘要列表，每項含 id / name 等字段；
                        後端不可用時返回空列表
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self._base_url}/api/backtest/strategies")
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                return []
            return data.get("data", [])

    async def get_strategy(self, strategy_id: int) -> dict[str, Any]:
        """獲取單個策略詳情。

        Args:
            strategy_id: 策略在後端的唯一 ID

        Returns:
            dict: 策略完整記錄（含 criteria / config / result）
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self._base_url}/api/backtest/strategies/{strategy_id}")
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {})

    async def get_market_overview(self) -> dict[str, Any]:
        """獲取市場概覽（dashboard summary）用於行情分析。

        Returns:
            dict: 儀表盤匯總數據（股票總數、漲跌統計等）
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self._base_url}/api/dashboard/summary")
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {})

    async def get_industries(self, code: str = None, industry: str = None) -> list[dict[str, Any]]:
        """查詢股票行業分類數據。

        Args:
            code: 指定股票代碼（可選）
            industry: 行業關鍵詞模糊查詢（可選）
        Returns:
            行業分類記錄列表
        """
        params = {}
        if code:
            params["code"] = code
        if industry:
            params["industry"] = industry
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self._base_url}/api/stock/industries", params=params)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                return []
            return data.get("data", [])

    async def get_industry_list(self) -> list[str]:
        """獲取所有不同行業名稱列表。

        Returns:
            list[str]: 去重後的行業名稱列表（如 ["J66證券期貨業", ...]）
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self._base_url}/api/stock/industries/list")
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                return []
            return data.get("data", [])

    async def health(self) -> bool:
        """檢查後端是否可用。

        Returns:
            bool: 後端健康檢查返回 200 時為 True，否則為 False
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/api/system/health")
                return resp.status_code == 200
        except Exception:
            return False


# 全局後端客戶端單例
backend_client = BackendClient()
