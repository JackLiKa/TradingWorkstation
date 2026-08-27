"""FTShare MCP 工具 — 金融數據查詢，150+ 金融數據工具。

通過 MCP streamableHttp 協議連接 FTShare MCP 服務。
提供 K線、估值、財報、資金流等結構化金融數據。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.chat.tool_base import ToolBase, ToolResult

logger = logging.getLogger("agent.chat.mcp.ftshare")

_FTSHARE_MCP_URL = "https://market.ft.tech/gateway/mcp"


class FtshareMcpTool(ToolBase):
    """FTShare MCP — 多資產量化數據查詢。"""

    @property
    def name(self) -> str:
        return "ftshare_mcp"

    @property
    def display_name(self) -> str:
        return "FTShare 金融數據"

    @property
    def description(self) -> str:
        return (
            "多資產量化數據查詢，提供 150+ 金融數據工具。"
            "可查詢股票、基金、外匯等標的的 K線、估值、財報、資金流等結構化數據。"
            "能徹底解決大模型的金融幻覺問題。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": (
                        "要調用的 FTShare 工具名稱（如 'get_kline', 'get_financial_report', "
                        "'get_capital_flow', 'get_valuation' 等）"
                    ),
                },
                "arguments": {
                    "type": "object",
                    "description": "傳遞給 FTShare 工具的參數（如股票代碼、日期範圍等）",
                },
            },
            "required": ["tool_name"],
        }

    async def execute(self, tool_name: str, arguments: dict[str, Any] | None = None, **kwargs) -> ToolResult:
        """通過 MCP 協議調用 FTShare 工具。"""
        arguments = arguments or {}
        try:
            result = await self._call_mcp_tool(tool_name, arguments)
            content = self._format_result(tool_name, result)
            citations = self._build_citations(tool_name, result)
            return ToolResult(success=True, content=content, citations=citations, raw_data=result)
        except Exception as e:
            logger.error(f"FTShare MCP 調用失敗: {e}", exc_info=True)
            return ToolResult(success=False, content=f"FTShare MCP 調用失敗: {e}", error=str(e))

    async def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """通過 MCP streamableHttp 協議調用工具。

        MCP streamableHttp 協議：
        1. POST initialize → 獲取 mcp-session-id
        2. POST notifications/initialized（帶 session-id）
        3. POST tools/call（帶 session-id）
        """
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
            init_resp = await client.post(_FTSHARE_MCP_URL, headers=headers, json=init_body)
            init_resp.raise_for_status()

            # 從響應 header 提取 mcp-session-id
            session_id = init_resp.headers.get("mcp-session-id", "")
            if session_id:
                headers["mcp-session-id"] = session_id

            # Step 2: 發送 initialized 通知（帶 session-id）
            notif_body = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            await client.post(_FTSHARE_MCP_URL, headers=headers, json=notif_body)

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
            resp = await client.post(_FTSHARE_MCP_URL, headers=headers, json=body)
            resp.raise_for_status()

            # MCP 可能返回 JSON 或 SSE 格式
            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                # 解析 SSE 格式
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

    async def list_available_tools(self) -> list[dict[str, Any]]:
        """列出 FTShare MCP 可用的全部工具（供前端展示）。"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Step 1: initialize 握手
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
                init_resp = await client.post(_FTSHARE_MCP_URL, headers=headers, json=init_body)
                init_resp.raise_for_status()

                # 提取 session-id
                session_id = init_resp.headers.get("mcp-session-id", "")
                if session_id:
                    headers["mcp-session-id"] = session_id

                # Step 2: initialized 通知
                notif_body = {"jsonrpc": "2.0", "method": "notifications/initialized"}
                await client.post(_FTSHARE_MCP_URL, headers=headers, json=notif_body)

                # Step 3: tools/list
                body = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                }
                resp = await client.post(_FTSHARE_MCP_URL, headers=headers, json=body)
                resp.raise_for_status()

                # 解析 SSE 或 JSON
                content_type = resp.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    for line in resp.text.split("\n"):
                        if line.startswith("data: ") and line.strip() != "data:":
                            try:
                                data = json.loads(line[6:])
                                return data.get("result", {}).get("tools", [])
                            except json.JSONDecodeError:
                                continue
                    return []
                else:
                    data = resp.json()
                    return data.get("result", {}).get("tools", [])
        except Exception as e:
            logger.warning(f"列出 FTShare 工具失敗: {e}")
            return []

    def _format_result(self, tool_name: str, result: dict[str, Any]) -> str:
        """格式化 MCP 結果為 Markdown。"""
        lines = [f"## FTShare 金融數據查詢結果\n"]
        lines.append(f"數據來源：FTShare MCP ({tool_name})\n")

        # MCP 結果格式：{ content: [{ type: "text", text: "..." }] }
        content_items = result.get("content", [])
        if isinstance(content_items, list):
            for item in content_items:
                if isinstance(item, dict) and item.get("type") == "text":
                    lines.append(item.get("text", ""))
                elif isinstance(item, str):
                    lines.append(item)
        elif isinstance(result, dict):
            # 直接的 dict 結果
            lines.append(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            lines.append(str(result))

        return "\n".join(lines)

    def _build_citations(self, tool_name: str, result: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "source": "FTShare MCP",
                "tool": tool_name,
                "title": f"FTShare {tool_name} 查詢結果",
                "url": _FTSHARE_MCP_URL,
            }
        ]
