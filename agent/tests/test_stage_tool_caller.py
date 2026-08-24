"""StageToolCaller 測試 — 驗證階段工具調用器的引用記錄和摘要生成。"""

import pytest

from app.agents.stages.tool_caller import StageToolCallRecord, StageToolCaller


class TestStageToolCaller:
    """StageToolCaller 單元測試。"""

    def test_empty_citations_summary(self):
        """無引用時返回空字符串。"""
        caller = StageToolCaller()
        assert caller.get_citations_summary() == ""

    def test_empty_tool_calls_summary(self):
        """無工具調用時返回空字符串。"""
        caller = StageToolCaller()
        assert caller.get_tool_calls_summary() == ""

    def test_citations_summary_with_data(self):
        """有引用時返回格式化摘要。"""
        caller = StageToolCaller()
        caller.citations = [
            {"source": "本地市場數據", "title": "上證指數行情", "url": "http://localhost:8090/api/stock"},
            {"source": "全網資訊檢索", "title": "A股存儲利好", "url": "https://example.com/news1"},
        ]
        summary = caller.get_citations_summary()
        assert "## 數據來源" in summary
        assert "本地市場數據" in summary
        assert "全網資訊檢索" in summary
        assert "http://localhost:8090/api/stock" in summary

    def test_citations_summary_dedup_by_url(self):
        """相同 URL 的引用去重。"""
        caller = StageToolCaller()
        caller.citations = [
            {"source": "來源1", "title": "標題A", "url": "https://example.com/1"},
            {"source": "來源2", "title": "標題B", "url": "https://example.com/1"},  # 同 URL
            {"source": "來源3", "title": "標題C", "url": "https://example.com/2"},
        ]
        summary = caller.get_citations_summary()
        # 應該只有 2 條（去重後）
        lines = [l for l in summary.split("\n") if l.startswith(("1.", "2.", "3.", "4."))]
        assert len(lines) == 2

    def test_tool_calls_summary_with_data(self):
        """有工具調用記錄時返回格式化摘要。"""
        caller = StageToolCaller()
        caller.tool_calls_log = [
            StageToolCallRecord(
                tool_name="local_market_data",
                display_name="本地市場數據",
                arguments={"action": "market_overview"},
                success=True,
                content_preview="市場概覽數據...",
                citations=[],
            ),
            StageToolCallRecord(
                tool_name="open_web_search",
                display_name="全網資訊檢索",
                arguments={"query": "A股存儲"},
                success=False,
                content_preview="",
                error="API 不可用",
            ),
        ]
        summary = caller.get_tool_calls_summary()
        assert "## 工具調用記錄" in summary
        assert "本地市場數據" in summary
        assert "全網資訊檢索" in summary
        assert "成功" in summary
        assert "失敗" in summary

    def test_to_dict_serialization(self):
        """to_dict 正確序列化。"""
        caller = StageToolCaller()
        caller.citations = [{"source": "test", "title": "t", "url": "u"}]
        caller.tool_calls_log = [
            StageToolCallRecord(
                tool_name="test_tool",
                display_name="測試工具",
                arguments={"k": "v"},
                success=True,
                content_preview="preview",
                citations=[],
            )
        ]
        d = caller.to_dict()
        assert d["total_calls"] == 1
        assert d["successful_calls"] == 1
        assert len(d["citations"]) == 1
        assert d["tool_calls"][0]["tool"] == "test_tool"

    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self):
        """調用不存在的工具返回失敗結果。"""
        caller = StageToolCaller()
        result = await caller.call("nonexistent_tool", foo="bar")
        assert result.success is False
        assert "不存在" in result.content
        assert len(caller.tool_calls_log) == 1
        assert caller.tool_calls_log[0].success is False
