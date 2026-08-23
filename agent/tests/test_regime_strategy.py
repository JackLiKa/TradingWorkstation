"""測試市場形態自適應策略指引 — regime_strategy.py。

覆蓋：
- 5 種市場形態的策略映射
- config 參數調整（牛市多倉位 vs 熊市少倉位）
- 策略指引文本生成
- 用戶覆蓋優先級
- 形態摘要
"""

import pytest

from app.services import regime_strategy


class TestRegimeStrategyMap:
    """測試形態映射完整性。"""

    def test_all_regime_types_covered(self):
        """所有形態類型都有映射。"""
        for regime_type in [
            "trending_up",
            "trending_down",
            "oscillation",
            "continuation_up",
            "continuation_down",
            "unknown",
        ]:
            assert regime_type in regime_strategy.REGIME_STRATEGY_MAP
            regime = regime_strategy.REGIME_STRATEGY_MAP[regime_type]
            assert "label" in regime
            assert "stance" in regime
            assert "description" in regime
            assert "criteria_guidance" in regime
            assert "config_adjustments" in regime
            assert "risk_rules" in regime

    def test_bull_market_aggressive(self):
        """牛市應該是進攻取向。"""
        regime = regime_strategy.REGIME_STRATEGY_MAP["trending_up"]
        assert regime["stance"] == "進攻"
        assert regime["config_adjustments"]["maxPositions"] >= 6
        assert regime["config_adjustments"]["stopLossPct"] >= 8  # 放寬止損

    def test_bear_market_defensive(self):
        """熊市應該是空倉防禦取向。"""
        regime = regime_strategy.REGIME_STRATEGY_MAP["trending_down"]
        assert regime["stance"] == "空倉防禦"
        assert regime["config_adjustments"]["maxPositions"] <= 2  # 極低倉位
        assert regime["config_adjustments"]["stopLossPct"] <= 5   # 嚴格止損

    def test_oscillation_flexible(self):
        """震盪市應該是靈活短線取向。"""
        regime = regime_strategy.REGIME_STRATEGY_MAP["oscillation"]
        assert regime["stance"] == "靈活短線"
        assert regime["config_adjustments"]["takeProfitPct"] is not None  # 設止盈
        assert regime["config_adjustments"]["maxPositions"] <= 5  # 中等倉位

    def test_bull_more_positions_than_bear(self):
        """牛市倉位應多於熊市。"""
        bull = regime_strategy.REGIME_STRATEGY_MAP["trending_up"]["config_adjustments"]["maxPositions"]
        bear = regime_strategy.REGIME_STRATEGY_MAP["trending_down"]["config_adjustments"]["maxPositions"]
        assert bull > bear

    def test_bear_stricter_stoploss_than_bull(self):
        """熊市止損應嚴於牛市。"""
        bull_sl = regime_strategy.REGIME_STRATEGY_MAP["trending_up"]["config_adjustments"]["stopLossPct"]
        bear_sl = regime_strategy.REGIME_STRATEGY_MAP["trending_down"]["config_adjustments"]["stopLossPct"]
        assert bear_sl < bull_sl


class TestGetRegimeStrategyGuidance:
    """測試策略指引文本生成。"""

    def test_bull_market_guidance(self):
        text = regime_strategy.get_regime_strategy_guidance("trending_up")
        assert "牛市" in text
        assert "進攻" in text
        assert "選股條件調修建議" in text
        assert "風險管理規則" in text
        assert "minPctChange" in text
        assert "必須遵循" in text or "必須根據" in text

    def test_bear_market_guidance(self):
        text = regime_strategy.get_regime_strategy_guidance("trending_down")
        assert "熊市" in text
        assert "空倉" in text
        assert "止損 4%" in text
        assert "防禦性板塊" in text

    def test_oscillation_guidance(self):
        text = regime_strategy.get_regime_strategy_guidance("oscillation")
        assert "震盪" in text
        assert "快進快出" in text
        assert "止盈" in text

    def test_unknown_regime_fallback(self):
        text = regime_strategy.get_regime_strategy_guidance("nonexistent_regime")
        assert "數據不足" in text or "謹慎" in text

    def test_guidance_contains_criteria_params(self):
        """指引應包含具體的選股參數建議。"""
        for regime_type in ["trending_up", "trending_down", "oscillation"]:
            text = regime_strategy.get_regime_strategy_guidance(regime_type)
            assert "minPctChange" in text or "minTurn" in text or "minRsi14" in text
            assert "maxRsi14" in text or "stopLossPct" in text or "minAmplitude" in text


class TestGetRegimeConfigAdjustments:
    """測試 config 參數調整。"""

    def test_bull_market_config(self):
        config = regime_strategy.get_regime_config_adjustments("trending_up")
        assert config["maxPositions"] == 8
        assert config["stopLossPct"] == 10
        assert config["rebalanceInterval"] == 3

    def test_bear_market_config(self):
        config = regime_strategy.get_regime_config_adjustments("trending_down")
        assert config["maxPositions"] == 1
        assert config["stopLossPct"] == 4
        assert config["rebalanceInterval"] == 10

    def test_oscillation_config(self):
        config = regime_strategy.get_regime_config_adjustments("oscillation")
        assert config["maxPositions"] == 4
        assert config["stopLossPct"] == 7
        assert config["takeProfitPct"] == 15

    def test_unknown_config(self):
        config = regime_strategy.get_regime_config_adjustments("unknown")
        assert config["maxPositions"] == 3
        assert config["stopLossPct"] == 7


class TestApplyRegimeToConfig:
    """測試 config 調整應用（含用戶覆蓋優先級）。"""

    def test_basic_apply(self):
        original = {
            "maxPositions": 5,
            "stopLossPct": None,
            "rebalanceInterval": 5,
            "holdingPeriod": 10,
            "initialCapital": 1_000_000,  # 不在形態調整中，保持原值
        }
        result = regime_strategy.apply_regime_to_config(original, "trending_up")
        assert result["maxPositions"] == 8       # 被牛市調整
        assert result["stopLossPct"] == 10       # 被牛市調整
        assert result["rebalanceInterval"] == 3  # 被牛市調整
        assert result["holdingPeriod"] == 7      # 被牛市調整（牛市短持有快換股）
        assert result["initialCapital"] == 1_000_000  # 不在調整中，保持原值

    def test_user_override_preserved(self):
        """用戶手動設置的字段不被形態調整覆蓋。"""
        original = {
            "maxPositions": 3,
            "stopLossPct": 6,
            "rebalanceInterval": 7,
        }
        user_overrides = {
            "maxPositions": 3,    # 用戶手動設置 3
            "stopLossPct": 6,     # 用戶手動設置 6
        }
        result = regime_strategy.apply_regime_to_config(
            original, "trending_up", user_overrides=user_overrides
        )
        # 用戶設置的保留
        assert result["maxPositions"] == 3   # 用戶值，不被牛市覆蓋為 8
        assert result["stopLossPct"] == 6    # 用戶值，不被牛市覆蓋為 10
        # 非用戶設置的被調整
        assert result["rebalanceInterval"] == 3  # 被牛市調整

    def test_bear_market_reduces_positions(self):
        """熊市應大幅降低倉位。"""
        original = {"maxPositions": 8, "stopLossPct": 10, "rebalanceInterval": 3}
        result = regime_strategy.apply_regime_to_config(original, "trending_down")
        assert result["maxPositions"] == 1       # 熊市極低倉位
        assert result["stopLossPct"] == 4        # 熊市嚴止損
        assert result["rebalanceInterval"] == 10 # 熊市慢調倉

    def test_none_user_override_ignored(self):
        """用戶覆蓋值為 None 時不保留（允許形態調整）。"""
        original = {"maxPositions": 5, "stopLossPct": None}
        user_overrides = {"stopLossPct": None}
        result = regime_strategy.apply_regime_to_config(
            original, "trending_up", user_overrides=user_overrides
        )
        assert result["stopLossPct"] == 10  # None 不算用戶設置，被牛市調整


class TestGetRegimeSummary:
    """測試形態摘要。"""

    def test_bull_summary(self):
        summary = regime_strategy.get_regime_summary("trending_up")
        assert summary["regime_type"] == "trending_up"
        assert "牛市" in summary["label"]
        assert summary["stance"] == "進攻"

    def test_bear_summary(self):
        summary = regime_strategy.get_regime_summary("trending_down")
        assert summary["regime_type"] == "trending_down"
        assert "熊市" in summary["label"]
        assert "空倉" in summary["stance"]

    def test_unknown_summary(self):
        summary = regime_strategy.get_regime_summary("nonexistent")
        assert summary["regime_type"] == "nonexistent"
        assert summary["stance"] == "謹慎"
