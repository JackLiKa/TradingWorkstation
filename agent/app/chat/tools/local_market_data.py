"""本地市場數據查詢工具 — 查詢 Java 後端的行情/指數/行業/新聞/選股 API。

這是 AI 聊天引擎與本地數據庫的橋樑。之前聊天 AI 只能調用外部網絡搜索，
無法訪問本地 MySQL 中已採集的歷史行情、行業分析、已入庫新聞等數據。

本工具復用 backend_client 的已封裝方法，通過 Java 後端 REST API 查詢：
- 市場概覽（dashboard summary）
- 指數歷史（上證/深證/創業板等）
- 板塊表現（行業漲跌排名）
- 行業景氣度（4 維度評分）
- 輪動信號
- 市場廣度（漲跌家數）
- 已入庫財經新聞（分頁查詢）
- 選股器（條件篩選）
- 數據範圍（最早/最新日期）
"""

from __future__ import annotations

import logging
from typing import Any

from app.chat.tool_base import ToolBase, ToolResult

logger = logging.getLogger("agent.chat.tools.local_market_data")


class LocalMarketDataTool(ToolBase):
    """本地市場數據查詢 — 查詢已採集的行情、行業、新聞數據。"""

    @property
    def name(self) -> str:
        return "local_market_data"

    @property
    def display_name(self) -> str:
        return "本地市場數據查詢"

    @property
    def description(self) -> str:
        return (
            "查詢本地數據庫中已採集的 A 股市場數據，包括：歷史行情、指數走勢、"
            "行業板塊表現、行業景氣度評分、輪動信號、市場廣度（漲跌家數）、"
            "已入庫財經新聞、選股器結果。"
            "這是獲取本地歷史數據的首選工具，比網絡搜索更準確、更完整。"
            "支持的操作類型（action）：market_overview, index_history, sector_performance, "
            "industry_prosperity, rotation_signals, market_breadth, local_news, "
            "screener, data_range。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "查詢操作類型：\n"
                        "market_overview - 市場概覽（指數+漲跌家數+板塊）\n"
                        "index_history - 指數歷史走勢（需傳 code）\n"
                        "sector_performance - 板塊多日表現\n"
                        "industry_prosperity - 行業景氣度評分\n"
                        "rotation_signals - 行業輪動信號\n"
                        "market_breadth - 市場廣度（漲跌家數）\n"
                        "local_news - 已入庫財經新聞（可選 channel 過濾）\n"
                        "screener - 選股器（需傳 criteria JSON）\n"
                        "data_range - 數據時間範圍"
                    ),
                    "enum": [
                        "market_overview",
                        "index_history",
                        "sector_performance",
                        "industry_prosperity",
                        "rotation_signals",
                        "market_breadth",
                        "local_news",
                        "screener",
                        "data_range",
                    ],
                },
                "code": {
                    "type": "string",
                    "description": "指數/股票代碼（如 sh.000001 上證指數），用於 index_history",
                },
                "days": {
                    "type": "integer",
                    "description": "回溯天數（默認 10），用於 index_history/sector_performance/market_breadth",
                    "default": 10,
                },
                "channel": {
                    "type": "string",
                    "description": "新聞頻道過濾（a-stock/global/us-stock/hk-stock/forex/commodity），用於 local_news",
                },
                "news_limit": {
                    "type": "integer",
                    "description": "新聞返回條數（默認 20），用於 local_news",
                    "default": 20,
                },
                "criteria": {
                    "type": "object",
                    "description": "選股條件 JSON，用於 screener。例如 {\"asOfDate\":\"2026-08-24\",\"adjustflag\":3,\"excludeSt\":true,\"maxResults\":50}",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, **kwargs) -> ToolResult:
        """執行本地數據查詢。"""
        try:
            from app.services.backend_client import backend_client

            if action == "market_overview":
                return await self._query_market_overview(backend_client)
            elif action == "index_history":
                code = kwargs.get("code", "sh.000001")
                days = kwargs.get("days", 10)
                return await self._query_index_history(backend_client, code, days)
            elif action == "sector_performance":
                days = kwargs.get("days", 10)
                return await self._query_sector_performance(backend_client, days)
            elif action == "industry_prosperity":
                return await self._query_industry_prosperity(backend_client)
            elif action == "rotation_signals":
                days = kwargs.get("days", 10)
                return await self._query_rotation_signals(backend_client, days)
            elif action == "market_breadth":
                days = kwargs.get("days", 10)
                return await self._query_market_breadth(backend_client, days)
            elif action == "local_news":
                channel = kwargs.get("channel")
                limit = kwargs.get("news_limit", 20)
                return await self._query_local_news(backend_client, channel, limit)
            elif action == "screener":
                criteria = kwargs.get("criteria", {})
                return await self._run_screener(backend_client, criteria)
            elif action == "data_range":
                return await self._query_data_range(backend_client)
            else:
                return ToolResult(
                    success=False,
                    content=f"未知的 action 類型: {action}",
                    error=f"unknown action: {action}",
                )
        except Exception as e:
            logger.error(f"本地數據查詢失敗 (action={action}): {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"本地數據查詢失敗: {e}",
                error=str(e),
            )

    async def _query_market_overview(self, client) -> ToolResult:
        """市場概覽。"""
        data = await client.get_market_overview()
        content = self._format_dict("市場概覽", data)
        return ToolResult(
            success=True,
            content=content,
            citations=[{"source": "本地數據庫", "title": "市場概覽", "type": "market_overview"}],
            raw_data=data,
        )

    async def _query_index_history(self, client, code: str, days: int) -> ToolResult:
        """指數歷史。"""
        data = await client.get_index_history(code, days)
        if not data:
            return ToolResult(
                success=False,
                content=f"指數 {code} 無歷史數據",
                error="no data",
            )
        lines = [f"## 指數歷史：{code}（最近 {days} 天）\n"]
        lines.append(f"| 日期 | 開盤 | 收盤 | 最高 | 最低 | 成交量 |")
        lines.append(f"|------|------|------|------|------|--------|")
        for row in data[:days]:
            lines.append(
                f"| {row.get('date', '')} | {row.get('open', '')} | "
                f"{row.get('close', '')} | {row.get('high', '')} | "
                f"{row.get('low', '')} | {row.get('volume', '')} |"
            )
        return ToolResult(
            success=True,
            content="\n".join(lines),
            citations=[{"source": "本地數據庫", "title": f"指數 {code} 歷史", "type": "index_history"}],
            raw_data=data,
        )

    async def _query_sector_performance(self, client, days: int) -> ToolResult:
        """板塊表現。"""
        data = await client.get_sector_performance(days)
        lines = [f"## 板塊多日表現（最近 {days} 天）\n"]
        if isinstance(data, list):
            for row in data[:20]:
                lines.append(f"- {row}")
        else:
            lines.append(self._format_dict_content(data))
        return ToolResult(
            success=True,
            content="\n".join(lines),
            citations=[{"source": "本地數據庫", "title": "板塊表現", "type": "sector_performance"}],
            raw_data=data,
        )

    async def _query_industry_prosperity(self, client) -> ToolResult:
        """行業景氣度。"""
        data = await client.get_industry_prosperity()
        lines = ["## 行業景氣度評分\n"]
        if isinstance(data, list):
            lines.append("| 行業 | 景氣度分 | 動量 | 估值 | 資金 |")
            lines.append("|------|---------|------|------|------|")
            for row in data[:30]:
                if isinstance(row, dict):
                    lines.append(
                        f"| {row.get('industry', '')} | {row.get('prosperity_score', '')} | "
                        f"{row.get('momentum_score', '')} | {row.get('valuation_score', '')} | "
                        f"{row.get('capital_score', '')} |"
                    )
                else:
                    lines.append(f"- {row}")
        else:
            lines.append(self._format_dict_content(data))
        return ToolResult(
            success=True,
            content="\n".join(lines),
            citations=[{"source": "本地數據庫", "title": "行業景氣度", "type": "industry_prosperity"}],
            raw_data=data,
        )

    async def _query_rotation_signals(self, client, days: int) -> ToolResult:
        """輪動信號。"""
        data = await client.get_rotation_signals(days)
        content = self._format_dict(f"行業輪動信號（最近 {days} 天）", data)
        return ToolResult(
            success=True,
            content=content,
            citations=[{"source": "本地數據庫", "title": "輪動信號", "type": "rotation_signals"}],
            raw_data=data,
        )

    async def _query_market_breadth(self, client, days: int) -> ToolResult:
        """市場廣度。"""
        data = await client.get_market_breadth(days)
        content = self._format_dict(f"市場廣度（最近 {days} 天）", data)
        return ToolResult(
            success=True,
            content=content,
            citations=[{"source": "本地數據庫", "title": "市場廣度", "type": "market_breadth"}],
            raw_data=data,
        )

    async def _query_local_news(self, client, channel: str | None, limit: int) -> ToolResult:
        """已入庫新聞查詢。"""
        import httpx
        from app.core.config import settings

        base = settings.backend_api_url
        url = f"{base}/api/news"
        if channel:
            url = f"{base}/api/news/channel/{channel}"
        params = {"page": 0, "size": min(limit, 50)}

        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get(url, params=params)
            resp.raise_for_status()
            body = resp.json()

        page_data = body.get("data", body)
        content_list = page_data.get("content", [])
        total = page_data.get("totalElements", len(content_list))

        lines = [f"## 已入庫財經新聞（{channel or '全部頻道'}，共 {total} 條，顯示前 {len(content_list)} 條）\n"]
        for item in content_list[:limit]:
            if isinstance(item, dict):
                title = item.get("title", "")
                pub_time = item.get("publishedAt", item.get("published_at", ""))
                uri = item.get("uri", item.get("url", ""))
                channel_val = item.get("channel", "")
                lines.append(f"### {title}")
                lines.append(f"- 時間: {pub_time}")
                lines.append(f"- 頻道: {channel_val}")
                if uri:
                    lines.append(f"- 來源: {uri}")
                lines.append("")

        return ToolResult(
            success=True,
            content="\n".join(lines),
            citations=[{"source": "本地數據庫", "title": f"入庫新聞 ({channel or '全部'})", "type": "local_news"}],
            raw_data=page_data,
        )

    async def _run_screener(self, client, criteria: dict) -> ToolResult:
        """選股器。"""
        if not criteria:
            criteria = {
                "asOfDate": None,  # 讓後端用最新日期
                "adjustflag": 3,
                "excludeSt": True,
                "maxResults": 50,
                "sortBy": "score",
            }
        data = await client.run_screener(criteria)
        content = self._format_dict("選股器結果", data)
        return ToolResult(
            success=True,
            content=content,
            citations=[{"source": "本地數據庫", "title": "選股結果", "type": "screener"}],
            raw_data=data,
        )

    async def _query_data_range(self, client) -> ToolResult:
        """數據時間範圍。"""
        latest_date = await client.get_latest_trade_date()
        earliest, latest = await client.get_data_range()
        content = (
            f"## 數據時間範圍\n\n"
            f"- 最早日期: {earliest}\n"
            f"- 最新日期: {latest}\n"
            f"- 最新交易日: {latest_date}\n"
        )
        return ToolResult(
            success=True,
            content=content,
            citations=[{"source": "本地數據庫", "title": "數據範圍", "type": "data_range"}],
            raw_data={"earliest": earliest, "latest": latest, "latest_trade_date": latest_date},
        )

    def _format_dict(self, title: str, data: Any) -> str:
        """格式化字典/列表為 Markdown。"""
        lines = [f"## {title}\n"]
        lines.append(self._format_dict_content(data))
        return "\n".join(lines)

    def _format_dict_content(self, data: Any, indent: int = 0) -> str:
        """遞歸格式化。"""
        lines = []
        prefix = "  " * indent
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{prefix}- **{k}**:")
                    lines.append(self._format_dict_content(v, indent + 1))
                else:
                    lines.append(f"{prefix}- {k}: {v}")
        elif isinstance(data, list):
            for i, item in enumerate(data[:20]):
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}{i + 1}. {self._format_dict_content(item, indent + 1)}")
                else:
                    lines.append(f"{prefix}{i + 1}. {item}")
            if len(data) > 20:
                lines.append(f"{prefix}... 共 {len(data)} 條")
        else:
            lines.append(f"{prefix}{data}")
        return "\n".join(lines)
