"""測試 Agent 憲章和 few-shot。"""
import pytest

from app.agents.charter import FULL_CHARTER, RECALL_SUMMARY, get_charter
from app.agents.few_shot import (
    get_few_shot,
    MARKET_NEWS_EXAMPLE,
    INDUSTRY_ANALYSIS_EXAMPLE,
    MARKET_ANALYSIS_EXAMPLE,
    STRATEGY_GENERATION_EXAMPLE,
    BACKTEST_REFLECTION_EXAMPLE,
    PROMPT_GENERATION_EXAMPLE,
    JUDGE_EXAMPLE,
)

# 所有已定義的 few-shot 示例
ALL_EXAMPLES = {
    "market_news": MARKET_NEWS_EXAMPLE,
    "industry_analysis": INDUSTRY_ANALYSIS_EXAMPLE,
    "market_analysis": MARKET_ANALYSIS_EXAMPLE,
    "strategy_generation": STRATEGY_GENERATION_EXAMPLE,
    "backtest_reflection": BACKTEST_REFLECTION_EXAMPLE,
    "prompt_generation": PROMPT_GENERATION_EXAMPLE,
    "judge": JUDGE_EXAMPLE,
}


class TestCharter:
    """測試 Agent 憲章。"""

    def test_full_charter_not_empty(self):
        assert len(FULL_CHARTER) > 100
        assert "量化交易" in FULL_CHARTER or "AI" in FULL_CHARTER

    def test_recall_summary_not_empty(self):
        assert len(RECALL_SUMMARY) > 50
        assert len(RECALL_SUMMARY) < len(FULL_CHARTER)

    def test_get_charter_first_iteration(self):
        """第一輪應該返回完整憲章。"""
        charter = get_charter(1)
        assert charter == FULL_CHARTER

    def test_get_charter_later_iteration(self):
        """後續輪次應該返回回憶摘要。"""
        charter = get_charter(5)
        assert charter == RECALL_SUMMARY

    def test_charter_contains_key_sections(self):
        """憲章應該包含關鍵章節。"""
        assert "背景" in FULL_CHARTER or "系統" in FULL_CHARTER
        assert "職責" in FULL_CHARTER or "規範" in FULL_CHARTER
        assert "約束" in FULL_CHARTER or "權限" in FULL_CHARTER
        assert "輸入" in FULL_CHARTER
        assert "輸出" in FULL_CHARTER


class TestFewShot:
    """測試 few-shot 示例。"""

    def test_get_few_shot_known_stage(self):
        """已知階段應該返回示例。"""
        for stage in ["market_news", "strategy_generation", "backtest_reflection", "judge"]:
            result = get_few_shot(stage)
            assert result, f"{stage} 應該有 few-shot 示例"

    def test_get_few_shot_unknown_stage(self):
        """未知階段應該返回空字符串。"""
        result = get_few_shot("unknown_stage")
        assert result == ""

    def test_all_stages_have_examples(self):
        """所有核心階段都應該有 few-shot。"""
        required = ["market_news", "industry_analysis", "market_analysis",
                    "strategy_generation", "backtest_reflection", "prompt_generation", "judge"]
        for stage in required:
            assert stage in ALL_EXAMPLES, f"{stage} 缺少 few-shot 定義"
            assert ALL_EXAMPLES[stage], f"{stage} few-shot 為空"
