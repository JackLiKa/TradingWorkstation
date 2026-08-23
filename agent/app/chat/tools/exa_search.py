"""Exa.ai 搜索工具 — 深度語義搜索，每日 150 次免費額度。

API 文檔：https://docs.exa.ai/reference/search
支持高質量語義級別的搜索，適合深度研報、技術分析等場景。
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from app.chat.tool_base import ToolBase, ToolResult

logger = logging.getLogger("agent.chat.tools.exa_search")

_EXA_API_URL = "https://api.exa.ai/search"
_EXA_CONTENT_URL = "https://api.exa.ai/contents"


class ExaSearchTool(ToolBase):
    """Exa.ai 深度語義搜索 — 高質量內容檢索。"""

    @property
    def name(self) -> str:
        return "exa_search"

    @property
    def display_name(self) -> str:
        return "Exa 深度語義搜索"

    @property
    def description(self) -> str:
        return (
            "深度語義搜索，適合針對特定主題（如新技術、公司深度研報）進行高質量檢索。"
            "每日有 150 次免費額度，請僅在 open_web_search 無法滿足深度需求時使用。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查詢（自然語言描述，非關鍵詞）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回結果數（默認 5）",
                    "default": 5,
                },
                "search_type": {
                    "type": "string",
                    "enum": ["keyword", "neural", "auto"],
                    "description": "搜索類型：keyword=關鍵詞, neural=語義, auto=自動（默認）",
                    "default": "auto",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5, search_type: str = "auto", **kwargs) -> ToolResult:
        """執行 Exa 搜索。"""
        api_key = os.environ.get("EXA_API_KEY", "")
        if not api_key:
            return ToolResult(
                success=False,
                content="Exa API Key 未配置（環境變量 EXA_API_KEY）",
                error="missing api key",
            )

        try:
            # 搜索 + 獲取內容摘要
            results = await self._search_and_get_contents(api_key, query, max_results, search_type)
            if results:
                content = self._format_results(query, results)
                citations = self._build_citations(results)
                return ToolResult(success=True, content=content, citations=citations, raw_data=results)
            else:
                return ToolResult(
                    success=False,
                    content=f"Exa 搜索未找到與「{query}」相關的結果",
                    error="no results",
                )
        except Exception as e:
            logger.error(f"Exa 搜索失敗: {e}", exc_info=True)
            return ToolResult(success=False, content=f"Exa 搜索失敗: {e}", error=str(e))

    async def _search_and_get_contents(
        self, api_key: str, query: str, max_results: int, search_type: str
    ) -> list[dict[str, Any]]:
        """搜索並獲取內容摘要。

        使用 /search 端點搜索（/contents 端點需要 ids/urls，不支持直接搜索）。
        """
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }
        body = {
            "query": query,
            "numResults": max_results,
            "type": search_type,
            "contents": {
                "text": {"maxCharacters": 500},  # 請求內容摘要
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 先用 /search 端點搜索
            resp = await client.post(_EXA_API_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("text", "")[:300] if item.get("text") else "",
                "source": "Exa.ai",
                "published_date": item.get("publishedDate", ""),
            })
        return results

    def _format_results(self, query: str, results: list[dict[str, Any]]) -> str:
        lines = [f"## Exa 搜索結果：{query}\n"]
        lines.append("數據來源：Exa.ai 語義搜索\n")
        for i, r in enumerate(results, 1):
            lines.append(f"### {i}. {r['title']}")
            lines.append(f"- URL: {r['url']}")
            if r.get("published_date"):
                lines.append(f"- 發布日期: {r['published_date']}")
            if r["snippet"]:
                lines.append(f"- 摘要: {r['snippet']}")
            lines.append("")
        return "\n".join(lines)

    def _build_citations(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "source": "Exa.ai",
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
                "date": r.get("published_date", ""),
            }
            for r in results
        ]
