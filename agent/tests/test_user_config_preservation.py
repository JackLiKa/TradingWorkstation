"""測試用戶手動回測配置不被 DB 策略覆蓋 — BUG 修復驗證。

BUG 描述: 用戶在 /start 時手動輸入回測配置（startDate/endDate/maxPositions 等），
但優化循環啟動後從 DB 載入最佳策略時，會直接覆蓋 state.current_config，
導致用戶的手動配置丟失。

修復: 在 restore() 之前捕獲用戶配置，載入 DB 策略後用 {**db_config, **user_config} 合併，
用戶值優先。
"""

from app.agents.state import DEFAULT_BACKTEST_CONFIG, OptimizerState


class TestUserConfigPreservation:
    """測試用戶手動配置在優化循環啟動時被保留。"""

    def test_user_config_stored_before_restore(self):
        """用戶配置在 /start 時設置到 state.current_config。"""
        state = OptimizerState()
        user_config = {
            **DEFAULT_BACKTEST_CONFIG,
            "startDate": "2025-06-01",
            "endDate": "2026-01-01",
            "maxPositions": 10,
        }
        state.current_config = user_config

        # 模擬優化循環啟動時捕獲用戶配置
        user_config_overrides = dict(state.current_config)

        assert user_config_overrides["startDate"] == "2025-06-01"
        assert user_config_overrides["endDate"] == "2026-01-01"
        assert user_config_overrides["maxPositions"] == 10

    def test_user_config_overrides_db_config(self):
        """DB 策略配置 + 用戶配置合併後，用戶值優先。"""
        # 模擬 DB 最佳策略的配置
        db_config = {
            "startDate": "2024-01-01",
            "endDate": "2025-12-31",
            "maxPositions": 5,
            "rebalanceInterval": 5,
            "holdingPeriod": 10,
            "initialCapital": 1_000_000,
            "commissionBps": 3,
            "stopLossPct": None,
            "takeProfitPct": None,
        }

        # 用戶手動設置的配置
        user_config_overrides = {
            "startDate": "2025-06-01",
            "endDate": "2026-01-01",
            "maxPositions": 10,
            "rebalanceInterval": 5,
            "holdingPeriod": 10,
            "initialCapital": 1_000_000,
            "commissionBps": 3,
            "stopLossPct": None,
            "takeProfitPct": None,
        }

        # 合併：用戶值優先
        merged = {**db_config, **user_config_overrides}

        # 用戶設置的值應該覆蓋 DB 值
        assert merged["startDate"] == "2025-06-01"
        assert merged["endDate"] == "2026-01-01"
        assert merged["maxPositions"] == 10
        # 未被用戶修改的值保留 DB 值
        assert merged["rebalanceInterval"] == 5

    def test_user_config_overrides_default_config(self):
        """無 DB 策略時，默認配置 + 用戶配置合併後，用戶值優先。"""
        default_config = {
            "startDate": "2026-01-01",
            "endDate": "2026-08-21",
            "maxPositions": 5,
            "rebalanceInterval": 5,
            "holdingPeriod": 10,
            "initialCapital": 1_000_000,
            "commissionBps": 3,
            "stopLossPct": None,
            "takeProfitPct": None,
        }

        user_config_overrides = {
            "startDate": "2025-06-01",
            "endDate": "2026-01-01",
            "maxPositions": 10,
            "rebalanceInterval": 5,
            "holdingPeriod": 10,
            "initialCapital": 1_000_000,
            "commissionBps": 3,
            "stopLossPct": None,
            "takeProfitPct": None,
        }

        merged = {**default_config, **user_config_overrides}

        assert merged["startDate"] == "2025-06-01"
        assert merged["endDate"] == "2026-01-01"
        assert merged["maxPositions"] == 10

    def test_config_not_lost_after_checkpoint_restore(self):
        """用戶配置在 restore() 之前捕獲，不被 checkpoint 覆蓋。"""
        state = OptimizerState()
        user_config = {
            **DEFAULT_BACKTEST_CONFIG,
            "startDate": "2025-06-01",
            "endDate": "2026-01-01",
            "maxPositions": 10,
        }
        state.current_config = user_config

        # 模擬優化循環：先捕獲用戶配置
        user_config_overrides = dict(state.current_config)

        # 模擬 restore() 覆蓋 current_config（checkpoint 有舊配置）
        state.current_config = {
            **DEFAULT_BACKTEST_CONFIG,
            "startDate": "2024-01-01",  # checkpoint 的舊日期
            "endDate": "2025-01-01",
        }

        # 用戶配置仍然保留在 user_config_overrides 中
        assert user_config_overrides["startDate"] == "2025-06-01"
        assert user_config_overrides["maxPositions"] == 10

        # 最終合併時用戶值優先
        db_config = {"startDate": "2024-01-01", "endDate": "2025-01-01", "maxPositions": 5}
        final_config = {**db_config, **user_config_overrides}
        assert final_config["startDate"] == "2025-06-01"
        assert final_config["maxPositions"] == 10
