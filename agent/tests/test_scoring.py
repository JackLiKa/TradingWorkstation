"""測試評分計算 — 綜合評分邏輯。"""

from app.agents.scoring import compute_composite_score


class TestComputeCompositeScore:
    """測試綜合評分計算。

    新公式: 收益(25%) + 回撤(20%) + 夏普(15%) + Calmar(15%) + 超額(10%) + 交易(10%) + 樣本(5%)
    """

    def test_high_return_low_drawdown_high_sharpe(self):
        """高收益 + 低回撤 + 高夏普 → 高分。"""
        stats = {"totalReturn": 30.0, "maxDrawdown": 5.0, "sharpe": 2.0}
        score = compute_composite_score(stats)
        # 收益 37.5, 回撤 90, 夏普 100, Calmar 0(annualReturn缺失), 超額 0, 交易 0, 樣本 0
        # → 37.5*0.25 + 90*0.20 + 100*0.15 + 0 + 0 + 0 + 0 = 9.375 + 18 + 15 = 42.375
        assert score == 42.38
        assert 0 <= score <= 100

    def test_zero_return(self):
        """零收益 + 中等回撤 + 零夏普 → 中低分。"""
        stats = {"totalReturn": 0, "maxDrawdown": 10.0, "sharpe": 0}
        score = compute_composite_score(stats)
        # 收益 0, 回撤 80, 夏普 50, Calmar 0, 超額 0, 交易 0, 樣本 0
        # → 0 + 80*0.20 + 50*0.15 + 0 + 0 + 0 + 0 = 16 + 7.5 = 23.5
        assert score == 23.5

    def test_negative_return(self):
        """負收益 → 懲罰。"""
        stats = {"totalReturn": -20.0, "maxDrawdown": 15.0, "sharpe": -0.5}
        score = compute_composite_score(stats)
        # 收益 -25, 回撤 70, 夏普 37.5, Calmar 0, 超額 0, 交易 0, 樣本 0
        # → -25*0.25 + 70*0.20 + 37.5*0.15 + 0 + 0 + 0 + 0 = -6.25 + 14 + 5.625 = 13.375
        assert score == 13.38
        assert score < 50  # 負收益應該低分

    def test_extreme_negative_return(self):
        """極端負收益 → 下限 -50。"""
        stats = {"totalReturn": -100.0, "maxDrawdown": 50.0, "sharpe": -3.0}
        score = compute_composite_score(stats)
        # 收益 -50 (下限), 回撤 0, 夏普 0, Calmar 0, 超額 0, 交易 0, 樣本 0
        # → -50*0.25 + 0 + 0 + 0 + 0 + 0 + 0 = -12.5
        assert score == -12.5

    def test_missing_fields(self):
        """缺少字段時用默認值 0。"""
        stats = {}
        score = compute_composite_score(stats)
        # 全 0 → 收益 0, 回撤 100, 夏普 50, Calmar 0, 超額 0, 交易 0, 樣本 0
        # → 0 + 100*0.20 + 50*0.15 + 0 + 0 + 0 + 0 = 20 + 7.5 = 27.5
        assert score == 27.5

    def test_calmar_bonus(self):
        """有年化收益和回撤時，Calmar 應加分。"""
        stats_no_calmar = {"totalReturn": 30.0, "maxDrawdown": 10.0, "sharpe": 1.5}
        stats_with_calmar = {"totalReturn": 30.0, "maxDrawdown": 10.0, "sharpe": 1.5, "annualReturn": 60.0}
        score_no = compute_composite_score(stats_no_calmar)
        score_with = compute_composite_score(stats_with_calmar)
        # Calmar = 60/10 = 6 → calmar_score = 100, 貢獻 100*0.15 = 15
        assert score_with > score_no
        assert score_with - score_no == 15.0  # Calmar 貢獻的差值

    def test_sample_size_penalty(self):
        """交易筆數 <30 時應有樣本量懲罰。"""
        stats_few = {"totalReturn": 20.0, "maxDrawdown": 10.0, "sharpe": 1.5, "totalTrades": 10}
        stats_enough = {"totalReturn": 20.0, "maxDrawdown": 10.0, "sharpe": 1.5, "totalTrades": 30}
        score_few = compute_composite_score(stats_few)
        score_enough = compute_composite_score(stats_enough)
        # 樣本分: 10/30*100=33.33 vs 30/30*100=100, 差值 (100-33.33)*0.05 ≈ 3.33
        # 交易分: 10*10=100 vs 30*10=100(封頂), 相同
        assert score_enough > score_few

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
