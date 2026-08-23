"""工具註冊表 — 統一管理所有可用工具（Tools + MCP）。

按需延遲初始化，避免啟動時加載所有工具的依賴。
"""

from __future__ import annotations

import logging
from typing import Any

from app.chat.tool_base import ToolBase

logger = logging.getLogger("agent.chat.registry")


class ToolRegistry:
    """工具註冊表 — 管理工具實例和元數據。"""

    def __init__(self):
        self._tools: dict[str, ToolBase] = {}
        self._initialized = False

    def register(self, tool: ToolBase) -> None:
        """註冊一個工具實例。"""
        self._tools[tool.name] = tool
        logger.info(f"[工具註冊] {tool.name} ({tool.display_name})")

    def get(self, name: str) -> ToolBase | None:
        """按名稱獲取工具。"""
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        """列出所有已註冊工具名稱。"""
        return list(self._tools.keys())

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """轉換為 OpenAI tools 格式列表。"""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def all_tools(self) -> list[ToolBase]:
        """返回所有工具實例。"""
        return list(self._tools.values())


# 全局註冊表實例
registry = ToolRegistry()


def init_tools() -> None:
    """初始化所有工具 — 延遲加載，僅在聊天功能首次使用時調用。"""
    if registry._initialized:
        return

    # === Tools（直接 API 調用）===
    try:
        from app.chat.tools.open_web_search import OpenWebSearchTool

        registry.register(OpenWebSearchTool())
    except Exception as e:
        logger.warning(f"工具 open_web_search 註冊失敗: {e}")

    try:
        from app.chat.tools.exa_search import ExaSearchTool

        registry.register(ExaSearchTool())
    except Exception as e:
        logger.warning(f"工具 exa_search 註冊失敗: {e}")

    try:
        from app.chat.tools.baidu_search import BaiduSearchTool

        registry.register(BaiduSearchTool())
    except Exception as e:
        logger.warning(f"工具 baidu_search 註冊失敗: {e}")

    try:
        from app.chat.tools.grep_app_search import GrepAppSearchTool

        registry.register(GrepAppSearchTool())
    except Exception as e:
        logger.warning(f"工具 grep_app_search 註冊失敗: {e}")

    try:
        from app.chat.tools.context7_search import Context7SearchTool

        registry.register(Context7SearchTool())
    except Exception as e:
        logger.warning(f"工具 context7_search 註冊失敗: {e}")

    # === MCP（MCP 協議客戶端）===
    try:
        from app.chat.mcp.ftshare_mcp import FtshareMcpTool

        registry.register(FtshareMcpTool())
    except Exception as e:
        logger.warning(f"MCP 工具 ftshare_mcp 註冊失敗: {e}")

    try:
        from app.chat.mcp.a_share_mcp import AShareMcpTool

        registry.register(AShareMcpTool())
    except Exception as e:
        logger.warning(f"MCP 工具 a_share_mcp 註冊失敗: {e}")

    registry._initialized = True
    logger.info(f"[工具註冊] 完成，共 {len(registry.list_names())} 個工具: {registry.list_names()}")
