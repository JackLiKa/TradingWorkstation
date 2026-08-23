"""百度搜索工具 — 千帆 AI 平台搜索 API，中文資訊與政策檢索。

使用百度千帆 AI 搜索 API 獲取國內中文資訊、A股政策文件、國內行業動態。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from app.chat.tool_base import ToolBase, ToolResult

logger = logging.getLogger("agent.chat.tools.baidu_search")

# 百度千帆搜索 API 端點
_QIANFAN_SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search"


class BaiduSearchTool(ToolBase):
    """百度千帆搜索 — 中文資訊與政策檢索。"""

    @property
    def name(self) -> str:
        return "baidu_search"

    @property
    def display_name(self) -> str:
        return "百度中文資訊搜索"

    @property
    def description(self) -> str:
        return (
            "中文資訊與政策檢索，適合查詢國內中文資訊、A股政策文件、國內行業動態。"
            "基於百度千帆 AI 搜索 API。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索關鍵詞（中文）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回結果數（默認 5）",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5, **kwargs) -> ToolResult:
        """執行百度搜索。"""
        api_key = os.environ.get("BAIDU_QIANFAN_API_KEY", "")
        if not api_key:
            return ToolResult(
                success=False,
                content="百度千帆 API Key 未配置（環境變量 BAIDU_QIANFAN_API_KEY）",
                error="missing api key",
            )

        try:
            results = await self._search(api_key, query, max_results)
            if results:
                content = self._format_results(query, results)
                citations = self._build_citations(results)
                return ToolResult(success=True, content=content, citations=citations, raw_data=results)
            else:
                return ToolResult(
                    success=False,
                    content=f"百度搜索未找到與「{query}」相關的結果",
                    error="no results",
                )
        except Exception as e:
            logger.error(f"百度搜索失敗: {e}", exc_info=True)
            return ToolResult(success=False, content=f"百度搜索失敗: {e}", error=str(e))

    async def _search(self, api_key: str, query: str, max_results: int) -> list[dict[str, Any]]:
        """調用百度千帆搜索 API。"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "messages": [
                {"role": "user", "content": query},
            ],
            "search_params": {
                "max_results": max_results,
                "search_type": "web",
            },
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(_QIANFAN_SEARCH_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        # 解析搜索結果（百度千帆返回格式：{ request_id, references: [...] }）
        results = []
        references = data.get("references", data.get("search_results", data.get("results", [])))
        for item in references[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", item.get("link", "")),
                "snippet": item.get("content", item.get("summary", item.get("snippet", "")))[:300],
                "source": "百度搜索",
                "date": item.get("date", item.get("publish_time", "")),
            })
        return results

    def _format_results(self, query: str, results: list[dict[str, Any]]) -> str:
        lines = [f"## 百度搜索結果：{query}\n"]
        lines.append("數據來源：百度千帆 AI 搜索\n")
        for i, r in enumerate(results, 1):
            lines.append(f"### {i}. {r['title']}")
            lines.append(f"- URL: {r['url']}")
            if r.get("date"):
                lines.append(f"- 日期: {r['date']}")
            if r["snippet"]:
                lines.append(f"- 摘要: {r['snippet']}")
            lines.append("")
        return "\n".join(lines)

    def _build_citations(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "source": "百度搜索",
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
                "date": r.get("date", ""),
            }
            for r in results
        ]
