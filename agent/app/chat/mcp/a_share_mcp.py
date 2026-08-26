"""a-share-mcp 工具 — A股深度歷史數據，基於 Baostock。

通過 MCP 協議連接 a-share-mcp 服務。
返回自動格式化的 Markdown 表格，適合 A股策略開發。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from app.chat.tool_base import ToolBase, ToolResult

logger = logging.getLogger("agent.chat.mcp.a_share")

# a-share-mcp 服務地址（默認本地，可通過環境變量配置）
_A_SHARE_MCP_URL = os.environ.get("A_SHARE_MCP_URL", "http://localhost:8101/mcp")


class AShareMcpTool(ToolBase):
    """a-share-mcp — A股深度歷史數據查詢。"""

    @property
    def name(self) -> str:
        return "a_share_mcp"

    @property
    def display_name(self) -> str:
        return "A股歷史數據"

    @property
    def description(self) -> str:
        return (
            "A股深度歷史數據查詢，基於 Baostock 數據源。"
            "適合 A股市場的歷史回測、盈利能力或償債能力分析。"
            "返回自動格式化的 Markdown 表格，極度適合 A股策略開發。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": (
                        "要調用的 a-share-mcp 工具名稱（如 'get_stock_history', "
                        "'get_profitability', 'get_solvency', 'get_stock_list' 等）"
                    ),
                },
                "arguments": {
                    "type": "object",
                    "description": "傳遞給工具的參數（如股票代碼、日期範圍、復權類型等）",
                },
            },
            "required": ["tool_name"],
        }

    async def execute(self, tool_name: str, arguments: dict[str, Any] | None = None, **kwargs) -> ToolResult:
        """通過 MCP 協議調用 a-share-mcp 工具。"""
        arguments = arguments or {}
        try:
            # 確保 a-share-mcp 子進程正在運行（自動重啟已崩潰的進程）
            from app.services.ashare_mcp_manager import ashare_mcp_manager
            await ashare_mcp_manager.ensure_running()

            result = await self._call_mcp_tool(tool_name, arguments)
            content = self._format_result(tool_name, result)
            citations = self._build_citations(tool_name, result)
            return ToolResult(success=True, content=content, citations=citations, raw_data=result)
        except Exception as e:
            logger.error(f"a-share-mcp 調用失敗: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"a-share-mcp 調用失敗: {e}。請確保 a-share-mcp 服務已啟動（URL: {_A_SHARE_MCP_URL}）",
                error=str(e),
            )

    async def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """通過 MCP 協議調用工具（含 initialize 握手 + session-id）。"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: MCP initialize 握手
            init_body = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "trading-workstation-agent", "version": "1.0"},
                },
            }
            init_resp = await client.post(_A_SHARE_MCP_URL, headers=headers, json=init_body)
            init_resp.raise_for_status()

            # 從響應 header 提取 mcp-session-id
            session_id = init_resp.headers.get("mcp-session-id", "")
            if session_id:
                headers["mcp-session-id"] = session_id

            # Step 2: 發送 initialized 通知（帶 session-id）
            notif_body = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            await client.post(_A_SHARE_MCP_URL, headers=headers, json=notif_body)

            # Step 3: 調用工具
            body = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }
            resp = await client.post(_A_SHARE_MCP_URL, headers=headers, json=body)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                text = resp.text
                for line in text.split("\n"):
                    if line.startswith("data: ") and line.strip() != "data:":
                        try:
                            data = json.loads(line[6:])
                            if "result" in data:
                                return data["result"]
                        except json.JSONDecodeError:
                            continue
                return {"error": "SSE 中未找到 result"}
            else:
                data = resp.json()
                if "result" in data:
                    return data["result"]
                elif "error" in data:
                    raise RuntimeError(f"MCP 錯誤: {data['error']}")
                return data

    def _format_result(self, tool_name: str, result: dict[str, Any]) -> str:
        lines = [f"## A股數據查詢結果\n"]
        lines.append(f"數據來源：a-share-mcp ({tool_name})，基於 Baostock\n")

        content_items = result.get("content", [])
        if isinstance(content_items, list):
            for item in content_items:
                if isinstance(item, dict) and item.get("type") == "text":
                    lines.append(item.get("text", ""))
                elif isinstance(item, str):
                    lines.append(item)
        elif isinstance(result, dict):
            lines.append(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            lines.append(str(result))

        return "\n".join(lines)

    def _build_citations(self, tool_name: str, result: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "source": "a-share-mcp (Baostock)",
                "tool": tool_name,
                "title": f"A股 {tool_name} 查詢結果",
                "url": _A_SHARE_MCP_URL,
            }
        ]
