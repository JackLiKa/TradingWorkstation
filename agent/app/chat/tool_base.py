"""聊天 AI 工具基类 — 所有工具（直接 API 调用）的統一接口。

工具分兩類：
1. Tools（直接 API 調用）— 在 tools/ 目錄下，每個工具獨立一個文件
2. MCP（MCP 協議客戶端）— 在 mcp/ 目錄下，通過 MCP 協議連接外部服務

兩者共用 ToolBase 抽象基類，確保 LLM 看到的 tool schema 一致。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("agent.chat.tools")


@dataclass
class ToolResult:
    """工具調用結果。"""

    success: bool
    content: str  # 返回給 LLM 的文本內容（Markdown 格式）
    citations: list[dict[str, Any]] = field(default_factory=list)  # 引用來源
    raw_data: Any = None  # 原始數據（供調試）
    error: str = ""


class ToolBase(ABC):
    """工具基類 — 定義工具的元數據和執行接口。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名稱（唯一標識，如 'open_web_search'）。"""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """工具顯示名稱（中文，如 '全網資訊檢索'）。"""

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（供 LLM 理解工具用途）。"""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """工具參數 JSON Schema（OpenAI function calling 格式）。"""

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """執行工具調用，返回 ToolResult。"""

    def to_openai_function(self) -> dict[str, Any]:
        """轉換為 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_openai_tool(self) -> dict[str, Any]:
        """轉換為 OpenAI tools 格式（與 to_openai_function 相同，別名保持語義清晰）。"""
        return self.to_openai_function()
