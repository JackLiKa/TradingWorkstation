"""Context7 搜索工具 — 檢索版本匹配的最新官方文檔。

Context7 提供庫/框架的最新官方文檔搜索，避免提供廢棄的 API 代碼。
適合查詢量化框架（VN.Py、QUANTAXIS）的用法、API 參數、代碼報錯。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.chat.tool_base import ToolBase, ToolResult

logger = logging.getLogger("agent.chat.tools.context7")

_CONTEXT7_API_URL = "https://context7.com/api/v1/search"


class Context7SearchTool(ToolBase):
    """Context7 文檔搜索 — 量化框架與代碼輔助。"""

    @property
    def name(self) -> str:
        return "context7_search"

    @property
    def display_name(self) -> str:
        return "Context7 文檔搜索"

    @property
    def description(self) -> str:
        return (
            "檢索版本匹配的最新官方文檔。適合查詢量化框架（VN.Py、QUANTAXIS）的用法、"
            "API 參數或遇到代碼報錯時查找最新文檔，避免提供廢棄的 API 代碼。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查詢（庫名 + 具體問題，如 'pandas DataFrame merge'）",
                },
                "library": {
                    "type": "string",
                    "description": "目標庫名（可選，如 'pandas', 'numpy'）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回結果數（默認 5）",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(
        self, query: str, library: str = "", max_results: int = 5, **kwargs
    ) -> ToolResult:
        """執行文檔搜索。"""
        try:
            results = await self._search(query, library, max_results)
            if results:
                content = self._format_results(query, results)
                citations = self._build_citations(results)
                return ToolResult(success=True, content=content, citations=citations, raw_data=results)
            else:
                return ToolResult(
                    success=False,
                    content=f"Context7 未找到與「{query}」相關的文檔",
                    error="no results",
                )
        except Exception as e:
            logger.error(f"Context7 搜索失敗: {e}", exc_info=True)
            return ToolResult(success=False, content=f"文檔搜索失敗: {e}", error=str(e))

    async def _search(self, query: str, library: str, max_results: int) -> list[dict[str, Any]]:
        """調用 Context7 API。"""
        params: dict[str, Any] = {"q": query}
        if library:
            params["library"] = library

        headers = {
            "User-Agent": "TradingWorkstation/1.0 (research)",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(_CONTEXT7_API_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("results", data.get("documents", []))[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", item.get("source_url", "")),
                    "snippet": item.get("content", item.get("snippet", ""))[:300],
                    "source": "Context7",
                    "library": item.get("library", library),
                    "version": item.get("version", ""),
                })
            return results
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Context7 API 可能尚未公開，降級到通用搜索建議
                return []
            raise

    def _format_results(self, query: str, results: list[dict[str, Any]]) -> str:
        lines = [f"## 文檔搜索結果：{query}\n"]
        lines.append("數據來源：Context7 官方文檔\n")
        for i, r in enumerate(results, 1):
            lines.append(f"### {i}. {r['title']}")
            if r.get("version"):
                lines.append(f"- 版本: {r['version']}")
            lines.append(f"- URL: {r['url']}")
            if r["snippet"]:
                lines.append(f"- 摘要: {r['snippet']}")
            lines.append("")
        return "\n".join(lines)

    def _build_citations(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "source": "Context7",
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"][:150],
                "version": r.get("version", ""),
            }
            for r in results
        ]
