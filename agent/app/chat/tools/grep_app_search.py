"""grep_app 搜索工具 — 在數百萬個 GitHub 倉庫中進行極速代碼搜索。

使用 grep.app 公開 API 搜索開源代碼。
適合查找量化策略源碼、開源庫用法示例。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.chat.tool_base import ToolBase, ToolResult

logger = logging.getLogger("agent.chat.tools.grep_app")

_GREP_APP_URL = "https://grep.app/api/search"


class GrepAppSearchTool(ToolBase):
    """grep.app 代碼搜索 — 開源代碼與策略檢索。"""

    @property
    def name(self) -> str:
        return "grep_app_search"

    @property
    def display_name(self) -> str:
        return "開源代碼搜索"

    @property
    def description(self) -> str:
        return (
            "在數百萬個 GitHub 倉庫中進行極速代碼搜索。"
            "適合查找開源社區的量化策略源碼、排查開源庫 Bug、尋找特定算法的實現。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "代碼搜索關鍵詞（如函數名、類名、代碼片段）",
                },
                "language": {
                    "type": "string",
                    "description": "編程語言過濾（如 python, java, typescript）",
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
        self, query: str, language: str = "", max_results: int = 5, **kwargs
    ) -> ToolResult:
        """執行代碼搜索。"""
        try:
            results = await self._search(query, language, max_results)
            if results:
                content = self._format_results(query, results)
                citations = self._build_citations(results)
                return ToolResult(success=True, content=content, citations=citations, raw_data=results)
            else:
                return ToolResult(
                    success=False,
                    content=f"grep.app 未找到與「{query}」相關的代碼",
                    error="no results",
                )
        except Exception as e:
            logger.error(f"grep.app 搜索失敗: {e}", exc_info=True)
            return ToolResult(success=False, content=f"代碼搜索失敗: {e}", error=str(e))

    async def _search(self, query: str, language: str, max_results: int) -> list[dict[str, Any]]:
        """調用 grep.app API。"""
        params: dict[str, Any] = {"q": query}
        if language:
            params["lang"] = language

        headers = {
            "User-Agent": "TradingWorkstation/1.0 (research)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_GREP_APP_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for hit in data.get("hits", {}).get("hits", [])[:max_results]:
            source = hit.get("_source", {})
            repo = source.get("repo", {})
            results.append({
                "title": f"{repo.get('raw', 'unknown')}/{source.get('path', '')}",
                "url": f"https://grep.app/search?q={query}",
                "snippet": source.get("content", "")[:300],
                "source": "grep.app",
                "repo": repo.get("raw", ""),
                "path": source.get("path", ""),
                "language": source.get("language", ""),
            })
        return results

    def _format_results(self, query: str, results: list[dict[str, Any]]) -> str:
        lines = [f"## 代碼搜索結果：{query}\n"]
        lines.append("數據來源：grep.app\n")
        for i, r in enumerate(results, 1):
            lines.append(f"### {i}. {r['title']}")
            lines.append(f"- 倉庫: {r['repo']}")
            lines.append(f"- 語言: {r['language']}")
            if r["snippet"]:
                lines.append(f"- 代碼片段:\n```\n{r['snippet'][:200]}\n```")
            lines.append("")
        return "\n".join(lines)

    def _build_citations(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "source": "grep.app",
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"][:150],
                "repo": r["repo"],
            }
            for r in results
        ]
