"""階段工具調用器 — 讓 AI 優化各階段能調用聊天工具 + MCP + 記錄引用出處。

設計目標：
1. 讓 AI 優化各階段（market_news / industry_analysis / strategy_generation 等）
   能像聊天引擎一樣調用註冊表中的工具（local_market_data / open_web_search / MCP 等）
2. 每次工具調用都記錄引用來源（citations），確保數據真實性可追溯
3. 工具調用結果注入到階段的 prompt 中，讓 LLM 基於真實數據生成分析

與聊天引擎的區別：
- 聊天引擎：LLM 自主決定調用哪些工具（function calling 循環）
- 階段工具調用器：階段代碼主動調用特定工具（確定性調用，不依賴 LLM 決策）
  這是因為優化各階段的數據需求是已知的（如 industry_analysis 一定需要行業數據），
  不需要 LLM 來決定調用哪些工具。

引用記錄：
- 每次工具調用後，ToolResult.citations 被收集到 tool_caller.citations
- 階段結束時，citations 被寫入 StageResult 和 ai_call_log
- 前端可顯示「本輪分析基於以下數據來源」
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("agent.stage.tools")


@dataclass
class StageToolCallRecord:
    """單次工具調用記錄 — 用於持久化和可追溯。"""

    tool_name: str  # 工具名稱（如 "local_market_data"）
    display_name: str  # 顯示名稱（如 "本地市場數據"）
    arguments: dict[str, Any]  # 調用參數
    success: bool  # 是否成功
    content_preview: str  # 結果預覽（前 500 字）
    citations: list[dict[str, Any]] = field(default_factory=list)  # 本次調用的引用來源
    error: str = ""  # 錯誤信息
    duration_ms: int = 0  # 耗時


class StageToolCaller:
    """階段工具調用器 — 在 AI 優化階段中調用聊天工具並記錄引用。

    用法：
        caller = StageToolCaller()
        result = await caller.call("local_market_data", action="market_overview")
        # result 是 ToolResult，citations 已自動收集
        # caller.citations 包含所有調用的引用
        # caller.tool_calls_log 包含所有調用記錄
    """

    def __init__(self):
        self._tools_initialized = False
        self.tool_calls_log: list[StageToolCallRecord] = []
        self.citations: list[dict[str, Any]] = []

    def _ensure_tools(self):
        """延遲初始化工具註冊表（共用聊天引擎的工具集）。"""
        if not self._tools_initialized:
            from app.chat.registry import init_tools

            init_tools()
            self._tools_initialized = True

    async def call(self, tool_name: str, **kwargs) -> Any:
        """調用指定工具並記錄結果。

        Args:
            tool_name: 工具名稱（如 "local_market_data", "open_web_search"）
            **kwargs: 工具參數

        Returns:
            ToolResult: 工具調用結果（含 content + citations）
        """
        import time

        from app.chat.tool_base import ToolResult

        self._ensure_tools()

        start_time = time.time()

        from app.chat.registry import registry

        tool = registry.get(tool_name)
        if not tool:
            record = StageToolCallRecord(
                tool_name=tool_name,
                display_name=tool_name,
                arguments=kwargs,
                success=False,
                content_preview="",
                error=f"工具 {tool_name} 不存在",
            )
            self.tool_calls_log.append(record)
            logger.warning(f"[階段工具] 工具 {tool_name} 不存在")
            return ToolResult(success=False, content=f"工具 {tool_name} 不存在", error="tool not found")

        try:
            logger.info(f"[階段工具] 調用 {tool_name}({kwargs})")
            result = await tool.execute(**kwargs)
            duration_ms = int((time.time() - start_time) * 1000)

            record = StageToolCallRecord(
                tool_name=tool_name,
                display_name=tool.display_name,
                arguments=kwargs,
                success=result.success,
                content_preview=result.content[:500],
                citations=result.citations,
                error=result.error,
                duration_ms=duration_ms,
            )
            self.tool_calls_log.append(record)
            self.citations.extend(result.citations)

            logger.info(
                f"[階段工具] {tool_name} 完成: success={result.success}, "
                f"citations={len(result.citations)}, duration={duration_ms}ms"
            )
            return result
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record = StageToolCallRecord(
                tool_name=tool_name,
                display_name=tool.display_name if tool else tool_name,
                arguments=kwargs,
                success=False,
                content_preview="",
                error=str(e),
                duration_ms=duration_ms,
            )
            self.tool_calls_log.append(record)
            logger.error(f"[階段工具] {tool_name} 執行異常: {e}", exc_info=True)
            return ToolResult(success=False, content=f"工具執行異常: {e}", error=str(e))

    def get_citations_summary(self) -> str:
        """生成引用來源摘要文本 — 用於注入到 LLM prompt 中。

        返回格式：
            ## 數據來源
            1. [本地市場數據] 上證指數近10日行情 (http://localhost:8090/...)
            2. [全網資訊檢索] A股存儲板塊利好 (https://...)
        """
        if not self.citations:
            return ""

        lines = ["## 數據來源（工具調用引用）"]
        seen_urls: set[str] = set()
        idx = 0
        for c in self.citations:
            url = c.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            idx += 1
            source = c.get("source", "未知")
            title = c.get("title", "")
            snippet = c.get("snippet", "")[:100]
            line = f"{idx}. [{source}] {title}"
            if url:
                line += f" ({url})"
            if snippet:
                line += f" — {snippet}"
            lines.append(line)
        return "\n".join(lines)

    def get_tool_calls_summary(self) -> str:
        """生成工具調用摘要文本 — 用於注入到 LLM prompt 中。

        返回格式：
            ## 工具調用記錄
            1. 本地市場數據 (action=market_overview) — 成功，返回 1200 字
            2. 全網資訊檢索 (query=A股存儲) — 成功，返回 800 字
        """
        if not self.tool_calls_log:
            return ""

        lines = ["## 工具調用記錄"]
        for i, record in enumerate(self.tool_calls_log, 1):
            status = "成功" if record.success else f"失敗({record.error})"
            args_str = json.dumps(record.arguments, ensure_ascii=False)
            content_len = len(record.content_preview)
            lines.append(
                f"{i}. {record.display_name} ({args_str}) — {status}，"
                f"返回 {content_len} 字"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """序列化為字典 — 用於寫入 ai_call_log 和 StageResult。"""
        return {
            "tool_calls": [
                {
                    "tool": r.tool_name,
                    "display_name": r.display_name,
                    "arguments": r.arguments,
                    "success": r.success,
                    "content_preview": r.content_preview,
                    "citations": r.citations,
                    "error": r.error,
                    "duration_ms": r.duration_ms,
                }
                for r in self.tool_calls_log
            ],
            "citations": self.citations,
            "total_calls": len(self.tool_calls_log),
            "successful_calls": sum(1 for r in self.tool_calls_log if r.success),
        }
