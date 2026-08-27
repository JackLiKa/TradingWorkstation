"""測試聊天引擎和工具註冊表。"""

import pytest
from app.chat.engine import ChatEngine, ChatMessage, ChatResult, TOOL_CALLING_PROVIDERS
from app.chat.tool_base import ToolBase, ToolResult
from app.chat.registry import ToolRegistry, init_tools, registry


class TestToolBase:
    """測試工具基類。"""

    def test_tool_base_is_abstract(self):
        """ToolBase 是抽象類，不能直接實例化。"""
        with pytest.raises(TypeError):
            ToolBase()

    def test_tool_result_dataclass(self):
        """ToolResult 數據類正確創建。"""
        result = ToolResult(success=True, content="test content")
        assert result.success is True
        assert result.content == "test content"
        assert result.citations == []
        assert result.error == ""

    def test_tool_result_with_citations(self):
        """ToolResult 帶引用來源。"""
        citations = [{"source": "test", "title": "Test", "url": "https://example.com"}]
        result = ToolResult(success=True, content="test", citations=citations)
        assert len(result.citations) == 1
        assert result.citations[0]["source"] == "test"


class TestToolRegistry:
    """測試工具註冊表。"""

    def test_registry_initial_state(self):
        """新註冊表為空。"""
        reg = ToolRegistry()
        assert reg.list_names() == []
        assert reg.all_tools() == []

    def test_registry_register_and_get(self):
        """註冊工具後可以獲取。"""
        reg = ToolRegistry()

        class FakeTool(ToolBase):
            @property
            def name(self):
                return "fake_tool"
            @property
            def display_name(self):
                return "Fake Tool"
            @property
            def description(self):
                return "A fake tool for testing"
            @property
            def parameters(self):
                return {"type": "object", "properties": {}}
            async def execute(self, **kwargs):
                return ToolResult(success=True, content="fake result")

        tool = FakeTool()
        reg.register(tool)
        assert "fake_tool" in reg.list_names()
        assert reg.get("fake_tool") is tool
        assert reg.get("nonexistent") is None

    def test_registry_to_openai_tools(self):
        """註冊表轉換為 OpenAI tools 格式。"""
        reg = ToolRegistry()

        class FakeTool(ToolBase):
            @property
            def name(self):
                return "fake_tool"
            @property
            def display_name(self):
                return "Fake Tool"
            @property
            def description(self):
                return "A fake tool"
            @property
            def parameters(self):
                return {"type": "object", "properties": {"query": {"type": "string"}}}
            async def execute(self, **kwargs):
                return ToolResult(success=True, content="fake")

        reg.register(FakeTool())
        tools = reg.to_openai_tools()
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "fake_tool"
        assert "query" in tools[0]["function"]["parameters"]["properties"]


class TestChatEngine:
    """測試聊天引擎。"""

    def test_chat_message_dataclass(self):
        """ChatMessage 數據類正確創建。"""
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_calls is None

    def test_chat_result_dataclass(self):
        """ChatResult 數據類正確創建。"""
        result = ChatResult(content="answer", provider="glm-5.2", model_name="glm-5.2")
        assert result.content == "answer"
        assert result.provider == "glm-5.2"
        assert result.citations == []
        assert result.tool_calls_log == []

    def test_select_provider_with_valid_preference(self):
        """工具調用供應商選擇應返回支持 function calling 的供應商。"""
        engine = ChatEngine()
        selected = engine._get_tool_calling_provider()
        # 應該返回 TOOL_CALLING_PROVIDERS 中的某個
        assert selected in TOOL_CALLING_PROVIDERS or selected == "deepseek-flash"

    def test_select_provider_with_empty_preference(self):
        """工具調用供應商降級鏈應包含多個供應商。"""
        engine = ChatEngine()
        selected = engine._get_tool_calling_provider()
        chain = engine._get_fallback_chain(selected)
        # 降級鏈至少包含一個供應商
        assert len(chain) >= 1
        assert selected in chain

    def test_build_messages_with_system_prompt(self):
        """構建消息列表應包含 system prompt。"""
        engine = ChatEngine()
        messages = [ChatMessage(role="user", content="hello")]
        result = engine._build_messages(messages)
        assert result[0]["role"] == "system"
        assert "量化交易" in result[0]["content"] or "投研" in result[0]["content"]
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "hello"

    def test_build_messages_with_history(self):
        """構建消息列表應包含完整歷史。"""
        engine = ChatEngine()
        messages = [
            ChatMessage(role="user", content="question 1"),
            ChatMessage(role="assistant", content="answer 1"),
            ChatMessage(role="user", content="question 2"),
        ]
        result = engine._build_messages(messages)
        assert len(result) == 4  # system + 3 messages
        assert result[0]["role"] == "system"
        assert result[1]["content"] == "question 1"
        assert result[2]["content"] == "answer 1"
        assert result[3]["content"] == "question 2"


class TestChatSystemPrompt:
    """測試聊天系統提示詞。"""

    def test_system_prompt_contains_role_definition(self):
        """系統提示詞包含角色定義。"""
        from app.chat.prompt import CHAT_SYSTEM_PROMPT
        assert "量化交易" in CHAT_SYSTEM_PROMPT
        assert "投研助手" in CHAT_SYSTEM_PROMPT

    def test_system_prompt_contains_tool_rules(self):
        """系統提示詞包含工具調用規則。"""
        from app.chat.prompt import CHAT_SYSTEM_PROMPT
        assert "open_web_search" in CHAT_SYSTEM_PROMPT
        assert "exa_search" in CHAT_SYSTEM_PROMPT
        assert "ftshare_mcp" in CHAT_SYSTEM_PROMPT
        assert "a_share_mcp" in CHAT_SYSTEM_PROMPT

    def test_system_prompt_contains_citation_requirement(self):
        """系統提示詞要求標註數據來源。"""
        from app.chat.prompt import CHAT_SYSTEM_PROMPT
        assert "數據來源" in CHAT_SYSTEM_PROMPT or "來源" in CHAT_SYSTEM_PROMPT
        assert "引用" in CHAT_SYSTEM_PROMPT or "追溯" in CHAT_SYSTEM_PROMPT

    def test_system_prompt_contains_error_handling(self):
        """系統提示詞包含容錯機制。"""
        from app.chat.prompt import CHAT_SYSTEM_PROMPT
        assert "容錯" in CHAT_SYSTEM_PROMPT or "暫無" in CHAT_SYSTEM_PROMPT
