"""測試評分計算 — 市場語境感知的綜合評分邏輯。"""

from app.agents.scoring import compute_composite_score


class TestComputeCompositeScore:
    """測試綜合評分計算。

    新公式: 收益(20%) + 回撤(15%) + 夏普(15%) + Calmar(10%) + 超額(15%) + 交易質量(15%) + 樣本(7%) + IR(3%)
    """

    def test_high_return_low_drawdown_high_sharpe(self):
        """高收益 + 低回撤 + 高夏普 → 高分。"""
        stats = {"totalReturn": 30.0, "maxDrawdown": 5.0, "sharpe": 2.0}
        score = compute_composite_score(stats)
        # 收益 37.5, 回撤 90, 夏普 100, Calmar 0, 超額 0, 交易質量 35, 樣本 0, IR 50
        # → 37.5*0.20 + 90*0.15 + 100*0.15 + 0 + 0 + 35*0.15 + 0 + 50*0.03
        # = 7.5 + 13.5 + 15 + 5.25 + 1.5 = 42.75
        assert score == 42.75
        assert 0 <= score <= 100

    def test_zero_return(self):
        """零收益 + 中等回撤 + 零夏普 → 中低分。"""
        stats = {"totalReturn": 0, "maxDrawdown": 10.0, "sharpe": 0}
        score = compute_composite_score(stats)
        # 收益 0, 回撤 80, 夏普 50, Calmar 0, 超額 0, 交易質量 35, 樣本 0, IR 50
        # → 0 + 80*0.15 + 50*0.15 + 0 + 0 + 35*0.15 + 0 + 50*0.03
        # = 12 + 7.5 + 5.25 + 1.5 = 26.25
        assert score == 26.25

    def test_negative_return(self):
        """負收益 → 懲罰。"""
        stats = {"totalReturn": -20.0, "maxDrawdown": 15.0, "sharpe": -0.5}
        score = compute_composite_score(stats)
        # 收益 -25, 回撤 70, 夏普 37.5, Calmar 0, 超額 0, 交易質量 35, 樣本 0, IR 50
        # → -25*0.20 + 70*0.15 + 37.5*0.15 + 0 + 0 + 35*0.15 + 0 + 50*0.03
        # = -5 + 10.5 + 5.625 + 5.25 + 1.5 = 17.88
        assert score == 17.88
        assert score < 50  # 負收益應該低分

    def test_extreme_negative_return(self):
        """極端負收益 → 下限。"""
        stats = {"totalReturn": -100.0, "maxDrawdown": 50.0, "sharpe": -3.0}
        score = compute_composite_score(stats)
        # 收益 -50, 回撤 0, 夏普 0, Calmar 0, 超額 0, 交易質量 35, 樣本 0, IR 50
        # → -50*0.20 + 0 + 0 + 0 + 0 + 35*0.15 + 0 + 50*0.03
        # = -10 + 5.25 + 1.5 = -3.25
        assert score == -3.25

    def test_missing_fields(self):
        """缺少字段時用默認值 0。"""
        stats = {}
        score = compute_composite_score(stats)
        # 全 0 → 收益 0, 回撤 100, 夏普 50, Calmar 0, 超額 0, 交易質量 35, 樣本 0, IR 50
        # → 0 + 100*0.15 + 50*0.15 + 0 + 0 + 35*0.15 + 0 + 50*0.03
        # = 15 + 7.5 + 5.25 + 1.5 = 29.25
        assert score == 29.25

    def test_calmar_bonus(self):
        """有年化收益和回撤時，Calmar 應加分。"""
        stats_no_calmar = {"totalReturn": 30.0, "maxDrawdown": 10.0, "sharpe": 1.5}
        stats_with_calmar = {"totalReturn": 30.0, "maxDrawdown": 10.0, "sharpe": 1.5, "annualReturn": 60.0}
        score_no = compute_composite_score(stats_no_calmar)
        score_with = compute_composite_score(stats_with_calmar)
        # Calmar = 60/10 = 6 → calmar_score = 100, 貢獻 100*0.10 = 10
        assert score_with > score_no
        assert score_with - score_no == 10.0  # Calmar 貢獻的差值

    def test_sample_size_penalty(self):
        """交易筆數 <30 時應有樣本量懲罰。"""
        stats_few = {"totalReturn": 20.0, "maxDrawdown": 10.0, "sharpe": 1.5, "totalTrades": 10}
        stats_enough = {"totalReturn": 20.0, "maxDrawdown": 10.0, "sharpe": 1.5, "totalTrades": 30}
        score_few = compute_composite_score(stats_few)
        score_enough = compute_composite_score(stats_enough)
        # 樣本分: 10/30*100=33.33 vs 100, 差值 (100-33.33)*0.07 ≈ 4.67
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


class TestZeroTradeMarketContextScoring:
    """測試 0 交易策略的市場語境感知評分。"""

    def test_zero_trade_market_crash_defensive(self):
        """市場大跌 + 空倉 = 主動防禦，應給中等分數。"""
        stats = {
            "totalReturn": 0,
            "maxDrawdown": 0,
            "sharpe": 0,
            "totalTrades": 0,
            "benchmarkReturn": -10.0,
            "excessReturn": 10.0,
        }
        score = compute_composite_score(stats)
        # 基準跌 10% → 30 + min(10*2, 20) = 30 + 20 = 50
        assert score == 50.0
        assert 30 <= score <= 50  # 主動防禦應在 30-50 區間

    def test_zero_trade_market_slight_decline(self):
        """市場小跌 + 空倉 = 尚可防禦。"""
        stats = {
            "totalReturn": 0,
            "maxDrawdown": 0,
            "sharpe": 0,
            "totalTrades": 0,
            "benchmarkReturn": -3.0,
            "excessReturn": 3.0,
        }
        score = compute_composite_score(stats)
        # 基準跌 3% → 15 + 3*3 = 24
        assert score == 24.0
        assert 15 <= score <= 30

    def test_zero_trade_market_oscillation(self):
        """市場震盪 + 空倉 = 無作為，應低分。"""
        stats = {
            "totalReturn": 0,
            "maxDrawdown": 0,
            "sharpe": 0,
            "totalTrades": 0,
            "benchmarkReturn": 2.0,
            "excessReturn": -2.0,
        }
        score = compute_composite_score(stats)
        # 基準漲 2% → max(5, 10-2*1) = 8
        assert score == 8.0
        assert score < 15  # 無作為應低分

    def test_zero_trade_market_rally_failure(self):
        """市場大漲 + 空倉 = 被動失效，應極低分。"""
        stats = {
            "totalReturn": 0,
            "maxDrawdown": 0,
            "sharpe": 0,
            "totalTrades": 0,
            "benchmarkReturn": 10.0,
            "excessReturn": -10.0,
        }
        score = compute_composite_score(stats)
        # 基準漲 10% → max(0, 5-(10-5)*0.5) = max(0, 2.5) = 2.5
        assert score == 2.5
        assert score < 5  # 被動失效應極低分

    def test_zero_trade_no_benchmark_backward_compatible(self):
        """無 benchmarkReturn 時，0 交易走正常公式（向後兼容）。"""
        stats = {"totalReturn": 0, "maxDrawdown": 0, "sharpe": 0, "totalTrades": 0}
        score = compute_composite_score(stats)
        # 走 _score_active_strategy：收益 0, 回撤 100, 夏普 50, 交易質量 35, IR 50
        # → 0 + 100*0.15 + 50*0.15 + 0 + 0 + 35*0.15 + 0 + 50*0.03
        # = 15 + 7.5 + 5.25 + 1.5 = 29.25
        assert score == 29.25

    def test_zero_trade_defensive_beats_passive_failure(self):
        """市場大跌時空倉分數應遠高於市場大漲時空倉。"""
        defensive = compute_composite_score({
            "totalTrades": 0, "benchmarkReturn": -8.0, "excessReturn": 8.0,
        })
        failure = compute_composite_score({
            "totalTrades": 0, "benchmarkReturn": 8.0, "excessReturn": -8.0,
        })
        assert defensive > failure
        assert defensive > 30  # 防禦至少 30+
        assert failure < 5  # 失效應低於 5


class TestTradeQualityScoring:
    """測試交易質量評分（勝率 + 盈虧比 + 活躍度）。"""

    def test_high_win_rate_bonus(self):
        """高勝率策略應加分。"""
        stats_low_wr = {
            "totalReturn": 15, "maxDrawdown": 10, "sharpe": 1.0,
            "totalTrades": 30, "winRate": 35, "profitLossRatio": 1.0,
        }
        stats_high_wr = {
            "totalReturn": 15, "maxDrawdown": 10, "sharpe": 1.0,
            "totalTrades": 30, "winRate": 65, "profitLossRatio": 1.0,
        }
        score_low = compute_composite_score(stats_low_wr)
        score_high = compute_composite_score(stats_high_wr)
        assert score_high > score_low

    def test_high_pl_ratio_bonus(self):
        """高盈虧比策略應加分。"""
        stats_low_pl = {
            "totalReturn": 15, "maxDrawdown": 10, "sharpe": 1.0,
            "totalTrades": 30, "winRate": 50, "profitLossRatio": 0.8,
        }
        stats_high_pl = {
            "totalReturn": 15, "maxDrawdown": 10, "sharpe": 1.0,
            "totalTrades": 30, "winRate": 50, "profitLossRatio": 2.5,
        }
        score_low = compute_composite_score(stats_low_pl)
        score_high = compute_composite_score(stats_high_pl)
        assert score_high > score_low

    def test_information_ratio_bonus(self):
        """正信息比率應比零信息比率得分高。"""
        stats_zero_ir = {
            "totalReturn": 15, "maxDrawdown": 10, "sharpe": 1.0,
            "totalTrades": 30, "informationRatio": 0,
        }
        stats_positive_ir = {
            "totalReturn": 15, "maxDrawdown": 10, "sharpe": 1.0,
            "totalTrades": 30, "informationRatio": 1.0,
        }
        score_zero = compute_composite_score(stats_zero_ir)
        score_positive = compute_composite_score(stats_positive_ir)
        assert score_positive > score_zero
