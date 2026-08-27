"""OpenWebSearch 工具 — 多引擎聚合搜索，無需 API Key。

使用免費的 web search API 獲取全網實時資訊。
優先使用 DuckDuckGo HTML 解析（無需 Key），降級到其他免費搜索。
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.chat.tool_base import ToolBase, ToolResult

logger = logging.getLogger("agent.chat.tools.open_web_search")


class OpenWebSearchTool(ToolBase):
    """全網資訊檢索 — 多引擎聚合搜索。"""

    @property
    def name(self) -> str:
        return "open_web_search"

    @property
    def display_name(self) -> str:
        return "全網資訊檢索"

    @property
    def description(self) -> str:
        return (
            "全網實時資訊搜索，支持多引擎聚合。獲取最新的市場新聞、政策變動、宏觀事件。"
            "無需 API Key，是獲取實時資訊的首選工具。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索關鍵詞（中英文均可）",
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
        """執行搜索。"""
        try:
            # 使用 DuckDuckGo Lite HTML 解析（無需 API Key）
            results = await self._search_duckduckgo(query, max_results)
            if results:
                content = self._format_results(query, results)
                citations = self._build_citations(results)
                return ToolResult(success=True, content=content, citations=citations, raw_data=results)
            else:
                return ToolResult(
                    success=False,
                    content=f"未找到與「{query}」相關的搜索結果",
                    error="no results",
                )
        except Exception as e:
            logger.error(f"OpenWebSearch 搜索失敗: {e}", exc_info=True)
            return ToolResult(success=False, content=f"搜索失敗: {e}", error=str(e))

    async def _search_duckduckgo(self, query: str, max_results: int) -> list[dict[str, str]]:
        """使用 DuckDuckGo Lite 搜索。"""
        url = "https://lite.duckduckgo.com/lite/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        data = {"q": query, "kl": "wt-wt"}  # wt-wt = no region bias

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.post(url, headers=headers, data=data)
            resp.raise_for_status()
            html = resp.text

        # 解析 DuckDuckGo Lite HTML（表格結構）
        # 注意：DuckDuckGo Lite 的 <a> 標籤中 href 在 class 之前：
        #   <a rel="nofollow" href="URL" class='result-link'>TITLE</a>
        results = []
        # 匹配結果鏈接和標題（兼容 href/class 順序 + 單引號/雙引號）
        link_pattern = re.compile(
            r'<a[^>]*href="([^"]+)"[^>]*class=["\']result-link["\'][^>]*>(.*?)</a>',
            re.S,
        )
        # DuckDuckGo Lite 的 snippet 在 <td class="result-snippet"> 中
        snippet_pattern = re.compile(
            r'<td[^>]*class=["\']result-snippet["\'][^>]*>(.*?)</td>',
            re.S,
        )

        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        # 如果 link_pattern 沒匹配到，用備選方案：直接找所有帶 result-link 的 <a>
        if not links:
            link_pattern_alt = re.compile(
                r'<a[^>]*class=["\']result-link["\'][^>]*>(.*?)</a>',
                re.S,
            )
            link_pattern_href = re.compile(r'href="([^"]+)"')
            alt_matches = link_pattern_alt.findall(html)
            alt_hrefs = link_pattern_href.findall(html)
            links = []
            for i, title_html in enumerate(alt_matches):
                if i < len(alt_hrefs):
                    links.append((alt_hrefs[i], title_html))

        # 如果 result-snippet class 不存在，用備選方案：提取所有非空 <td> 內容
        if not snippets and links:
            all_tds = re.findall(r'<td[^>]*>(.*?)</td>', html, re.S)
            meaningful_tds = []
            for td in all_tds:
                clean = re.sub(r"<[^>]+>", "", td).strip()
                clean = clean.replace("&nbsp;", "").strip()
                if clean and len(clean) > 10:
                    meaningful_tds.append(clean)
            snippets = []
            for i in range(len(links)):
                idx = (i + 1) * 2
                if idx < len(meaningful_tds):
                    snippets.append(meaningful_tds[idx])
                else:
                    snippets.append("")

        for i, (href, title) in enumerate(links[:max_results]):
            # 清理 HTML 標籤
            clean_title = re.sub(r"<[^>]+>", "", title).strip()
            clean_href = href.replace("&l=1", "")  # 去除重定向參數
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else ""
            snippet = snippet.replace("&nbsp;", "").strip()

            # DuckDuckGo 的鏈接可能是重定向的，提取實際 URL
            if "uddg=" in clean_href:
                import urllib.parse

                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(clean_href).query)
                clean_href = parsed.get("uddg", [clean_href])[0]

            results.append({
                "title": clean_title,
                "url": clean_href,
                "snippet": snippet,
                "source": "DuckDuckGo",
            })

        return results

    def _format_results(self, query: str, results: list[dict[str, str]]) -> str:
        """格式化搜索結果為 Markdown。"""
        lines = [f"## 搜索結果：{query}\n"]
        lines.append(f"數據來源：OpenWebSearch (DuckDuckGo)\n")
        for i, r in enumerate(results, 1):
            lines.append(f"### {i}. {r['title']}")
            lines.append(f"- URL: {r['url']}")
            if r["snippet"]:
                lines.append(f"- 摘要: {r['snippet']}")
            lines.append("")
        return "\n".join(lines)

    def _build_citations(self, results: list[dict[str, str]]) -> list[dict[str, Any]]:
        """構建引用來源。"""
        return [
            {
                "source": "OpenWebSearch",
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
            }
            for r in results
        ]
