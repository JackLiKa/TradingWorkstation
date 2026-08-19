"""測試評分計算 — 綜合評分邏輯。"""
import pytest

from app.agents.scoring import compute_composite_score


class TestComputeCompositeScore:
    """測試綜合評分計算。"""

    def test_high_return_low_drawdown_high_sharpe(self):
        """高收益 + 低回撤 + 高夏普 → 高分。"""
        stats = {"totalReturn": 30.0, "maxDrawdown": 5.0, "sharpe": 2.0}
        score = compute_composite_score(stats)
        # 收益 60, 回撤 90, 夏普 100 → 60*0.4 + 90*0.3 + 100*0.3 = 24+27+30 = 81
        assert score == 81.0
        assert 0 <= score <= 100

    def test_zero_return(self):
        """零收益 + 中等回撤 + 零夏普 → 中低分。"""
        stats = {"totalReturn": 0, "maxDrawdown": 10.0, "sharpe": 0}
        score = compute_composite_score(stats)
        # 收益 0, 回撤 80, 夏普 50 → 0 + 24 + 15 = 39
        assert score == 39.0

    def test_negative_return(self):
        """負收益 → 懲罰。"""
        stats = {"totalReturn": -20.0, "maxDrawdown": 15.0, "sharpe": -0.5}
        score = compute_composite_score(stats)
        # 收益 -40, 回撤 70, 夏普 37.5 → -16 + 21 + 11.25 = 16.25
        assert score == 16.25
        assert score < 50  # 負收益應該低分

    def test_extreme_negative_return(self):
        """極端負收益 → 下限 -50。"""
        stats = {"totalReturn": -100.0, "maxDrawdown": 50.0, "sharpe": -3.0}
        score = compute_composite_score(stats)
        # 收益 -50 (下限), 回撤 0, 夏普 0 → -20 + 0 + 0 = -20
        assert score == -20.0

    def test_missing_fields(self):
        """缺少字段時用默認值 0。"""
        stats = {}
        score = compute_composite_score(stats)
        # 全 0 → 收益 0, 回撤 100, 夏普 50 → 0 + 30 + 15 = 45
        assert score == 45.0

    def test_score_range(self):
        """評分應該在合理範圍。"""
        test_cases = [
            {"totalReturn": 50, "maxDrawdown": 0, "sharpe": 3},
            {"totalReturn": -30, "maxDrawdown": 40, "sharpe": -1},
            {"totalReturn": 10, "maxDrawdown": 8, "sharpe": 0.8},
        ]
        for stats in test_cases:
            score = compute_composite_score(stats)
            assert -100 <= score <= 100, f"score {score} out of range for {stats}"

    def test_score_precision(self):
        """評分保留兩位小數。"""
        stats = {"totalReturn": 15.5, "maxDrawdown": 7.3, "sharpe": 1.2}
        score = compute_composite_score(stats)
        # 檢查最多兩位小數
        assert round(score, 2) == score
