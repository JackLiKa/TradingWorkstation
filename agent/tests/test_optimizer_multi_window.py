"""測試 optimizer 的多窗口回測評分和 max_stagnant_iterations 無進展終止。

覆蓋：
- multi_window_backtest=false 時用單一窗口（保持兼容）
- multi_window_backtest=true 時用 3 個窗口（90/180/365 天）
- 窗口權重 0.5/0.3/0.2 正確加權平均
- max_stagnant_iterations=0 時不限制（連續低分繼續）
- max_stagnant_iterations=3 時連續 3 輪 Δscore<1 自動停止

所有後端調用均用 mock，不依賴真實後端或 LLM。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents import optimizer
from app.agents.optimizer import (
    MULTI_WINDOW_DAYS,
    MULTI_WINDOW_WEIGHTS,
    STAGNANT_SCORE_DELTA_THRESHOLD,
    _build_window_config,
    _run_multi_window_backtest,
    _weighted_average_score,
)
from app.agents.scoring import compute_composite_score
from app.agents.state import StageResult


# ===========================================================================
# 純函數測試 — 加權平均評分
# ===========================================================================
class TestWeightedAverageScore:
    """測試 _weighted_average_score 純函數。"""

    def test_weights_05_03_02(self):
        """權重 0.5/0.3/0.2 應正確加權平均。"""
        scores = [80.0, 70.0, 60.0]
        weights = [0.5, 0.3, 0.2]
        # 80*0.5 + 70*0.3 + 60*0.2 = 40 + 21 + 12 = 73
        assert _weighted_average_score(scores, weights) == 73.0

    def test_all_equal_scores(self):
        """所有窗口評分相同時，加權平均等於該評分。"""
        assert _weighted_average_score([50.0, 50.0, 50.0], [0.5, 0.3, 0.2]) == 50.0

    def test_empty_scores(self):
        """空列表應返回 0.0。"""
        assert _weighted_average_score([], [0.5, 0.3, 0.2]) == 0.0

    def test_mismatched_lengths(self):
        """scores 和 weights 長度不一致應返回 0.0。"""
        assert _weighted_average_score([80.0, 70.0], [0.5, 0.3, 0.2]) == 0.0

    def test_zero_total_weight(self):
        """權重總和為 0 時應返回 0.0（避免除零）。"""
        assert _weighted_average_score([80.0, 70.0, 60.0], [0.0, 0.0, 0.0]) == 0.0

    def test_module_constants_match_spec(self):
        """模塊常量應符合規格：90/180/365 天，權重 0.5/0.3/0.2。"""
        assert MULTI_WINDOW_DAYS == [90, 180, 365]
        assert MULTI_WINDOW_WEIGHTS == [0.5, 0.3, 0.2]
        assert sum(MULTI_WINDOW_WEIGHTS) == pytest.approx(1.0)
        assert len(MULTI_WINDOW_DAYS) == len(MULTI_WINDOW_WEIGHTS) == 3

    def test_stagnant_threshold_is_one(self):
        """無進展閾值應為 1.0（Δscore < 1 視為無進展）。"""
        assert STAGNANT_SCORE_DELTA_THRESHOLD == 1.0


# ===========================================================================
# 純函數測試 — 構建窗口配置
# ===========================================================================
class TestBuildWindowConfig:
    """測試 _build_window_config 純函數。"""

    def test_90_day_window(self):
        """90 天窗口應將 startDate 回推 90 天。"""
        base = {"startDate": "2026-01-01", "endDate": "2026-08-20", "holdingPeriod": 10}
        cfg = _build_window_config(base, 90)
        assert cfg["startDate"] == "2026-05-22"  # 2026-08-20 - 90 天
        assert cfg["endDate"] == "2026-08-20"
        assert cfg["holdingPeriod"] == 10

    def test_180_day_window(self):
        """180 天窗口應將 startDate 回推 180 天。"""
        base = {"startDate": "2026-01-01", "endDate": "2026-08-20"}
        cfg = _build_window_config(base, 180)
        assert cfg["startDate"] == "2026-02-21"  # 2026-08-20 - 180 天

    def test_365_day_window(self):
        """365 天窗口應將 startDate 回推 365 天。"""
        base = {"startDate": "2026-01-01", "endDate": "2026-08-20"}
        cfg = _build_window_config(base, 365)
        assert cfg["startDate"] == "2025-08-20"  # 2026-08-20 - 365 天

    def test_does_not_mutate_base(self):
        """構建窗口配置不應修改原始 base_config。"""
        base = {"startDate": "2026-01-01", "endDate": "2026-08-20", "maxPositions": 5}
        original = dict(base)
        _build_window_config(base, 90)
        assert base == original, "原始配置不應被修改"

    def test_preserves_other_fields(self):
        """窗口配置應保留 base_config 的其餘字段。"""
        base = {
            "startDate": "2026-01-01",
            "endDate": "2026-08-20",
            "rebalanceInterval": 5,
            "holdingPeriod": 10,
            "maxPositions": 5,
            "initialCapital": 1_000_000,
            "commissionBps": 3,
        }
        cfg = _build_window_config(base, 90)
        for key in ("rebalanceInterval", "holdingPeriod", "maxPositions", "initialCapital", "commissionBps"):
            assert cfg[key] == base[key]

    def test_missing_end_date_keeps_original(self):
        """endDate 缺失時應保留原 startDate（不報錯）。"""
        base = {"startDate": "2026-01-01", "holdingPeriod": 10}
        cfg = _build_window_config(base, 90)
        assert cfg["startDate"] == "2026-01-01"

    def test_invalid_end_date_keeps_original(self):
        """endDate 無法解析時應保留原 startDate（不報錯）。"""
        base = {"startDate": "2026-01-01", "endDate": "not-a-date"}
        cfg = _build_window_config(base, 90)
        assert cfg["startDate"] == "2026-01-01"


# ===========================================================================
# 異步函數測試 — 多窗口回測（mock backend_client）
# ===========================================================================
def _stats_for_score(target_score: float) -> dict:
    """構建能產生指定 composite_score 的回測統計。

    新公式: 收益(25%) + 回撤(20%) + 夏普(15%) + Calmar(15%) + 超額(10%) + 交易(10%) + 樣本(5%)

    策略：用較大 maxDrawdown 避免 Calmar 封頂，同時調整 totalReturn 達到目標分。
    固定 sharpe=2（sharpe_score=100→15 分）、totalTrades=30（trade_score=100→10 分, sample_score=100→5 分）、
    excessReturn=totalReturn、annualReturn=totalReturn*2。

    設 maxDrawdown=20（drawdown_score=60→12 分）：
    Calmar = totalReturn*2/20 = totalReturn*0.1, calmar_score = min(totalReturn*0.1*33.3, 100)
    當 totalReturn ≤ 30: calmar_score = totalReturn*3.33
    composite = totalReturn*1.25*0.25 + 60*0.20 + 100*0.15 + totalReturn*3.33*0.15 + totalReturn*3*0.10 + 100*0.10 + 100*0.05
             = totalReturn*0.3125 + 12 + 15 + totalReturn*0.4995 + totalReturn*0.3 + 10 + 5
             = totalReturn*1.112 + 42
    故 totalReturn = (target - 42) / 1.112
    """
    total_return = (target_score - 42) / 1.112
    return {
        "totalReturn": total_return,
        "maxDrawdown": 20,
        "sharpe": 2,
        "excessReturn": total_return,
        "totalTrades": 30,
        "annualReturn": total_return * 2,
    }


class TestRunMultiWindowBacktest:
    """測試 _run_multi_window_backtest 異步函數（mock backend_client）。"""

    def test_three_backtest_calls(self):
        """啟用多窗口時應調用 run_backtest 3 次（每窗口一次）。"""
        call_count = 0

        async def fake_run_backtest(criteria, config):
            nonlocal call_count
            call_count += 1
            return {"statistics": {"totalReturn": 10, "maxDrawdown": 5, "sharpe": 0}, "logLines": []}

        with patch.object(optimizer, "backend_client") as mock_bc:
            mock_bc.run_backtest = fake_run_backtest
            score, result = asyncio.run(
                _run_multi_window_backtest({"asOfDate": "2026-01-01"}, {"endDate": "2026-08-20"})
            )
        assert call_count == 3
        assert "statistics" in result

    def test_weighted_average_correct(self):
        """3 個窗口不同評分時，加權平均應正確（0.5/0.3/0.2）。"""
        # 窗口順序 90/180/365 → 評分 60/50/40
        window_scores = [60.0, 50.0, 40.0]
        idx = 0

        async def fake_run_backtest(criteria, config):
            nonlocal idx
            stats = _stats_for_score(window_scores[idx])
            idx += 1
            return {"statistics": stats, "logLines": []}

        with patch.object(optimizer, "backend_client"):
            optimizer.backend_client.run_backtest = fake_run_backtest
            score, result = asyncio.run(
                _run_multi_window_backtest({"asOfDate": "2026-01-01"}, {"endDate": "2026-08-20"})
            )
        # 60*0.5 + 50*0.3 + 40*0.2 = 30 + 15 + 8 = 53（容忍 _stats_for_score 浮點誤差）
        assert score == pytest.approx(53.0, abs=1.0)

    def test_primary_result_is_longest_window(self):
        """主窗口（365 天，最後一個）的回測結果應被返回。"""
        idx = 0

        async def fake_run_backtest(criteria, config):
            nonlocal idx
            idx += 1
            # 最後一個窗口（365 天）返回帶標記的結果
            marker = "primary" if idx == 3 else f"window_{idx}"
            return {"statistics": {"totalReturn": 10, "maxDrawdown": 5, "sharpe": 0}, "logLines": [], "marker": marker}

        with patch.object(optimizer, "backend_client"):
            optimizer.backend_client.run_backtest = fake_run_backtest
            score, result = asyncio.run(
                _run_multi_window_backtest({"asOfDate": "2026-01-01"}, {"endDate": "2026-08-20"})
            )
        assert result.get("marker") == "primary"

    def test_uses_correct_window_days(self):
        """每個窗口的 config.startDate 應對應 90/180/365 天回推。"""
        seen_starts = []

        async def fake_run_backtest(criteria, config):
            seen_starts.append(config["startDate"])
            return {"statistics": {"totalReturn": 0, "maxDrawdown": 0, "sharpe": 0}, "logLines": []}

        with patch.object(optimizer, "backend_client"):
            optimizer.backend_client.run_backtest = fake_run_backtest
            asyncio.run(_run_multi_window_backtest({"asOfDate": "2026-01-01"}, {"endDate": "2026-08-20"}))
        # endDate=2026-08-20
        assert seen_starts[0] == "2026-05-22"  # 90 天
        assert seen_starts[1] == "2026-02-21"  # 180 天
        assert seen_starts[2] == "2025-08-20"  # 365 天


# ===========================================================================
# 集成測試 — run_optimization_loop 中的多窗口開關和無進展終止
# ===========================================================================
@pytest.fixture
def reset_state():
    """每個測試前重置 optimizer 全局狀態。"""
    s = optimizer.state
    s.running = False
    s.started_at = ""
    s.stopped_at = ""
    s.status_message = ""
    s.current_iteration = 0
    s.best_score = -999
    s.best_iteration = 0
    s.best_strategy_id = None
    s.best_criteria = {}
    s.best_config = {}
    s.current_criteria = {}
    s.current_config = {}
    s.current_reflection = ""
    s.current_next_prompt = ""
    s.current_market_context = ""
    s.current_stage = ""
    s.current_stage_status = ""
    s.iterations = []
    s.current_stage_results = []
    yield s
    # 清理 stop event
    optimizer._stop_event.clear()


def _make_stage_result(output: str = "ok", stage_name: str = "test") -> StageResult:
    """構建一個簡單的 StageResult。"""
    return StageResult(stage_name=stage_name, output=output, judge_score=80.0, judge_passed=True)


def _setup_loop_mocks(
    backtest_side_effect,
    *,
    best_score_from_db: float = -999,
    multi_window: bool = False,
    max_stagnant: int = 0,
    optimization_interval: int = 0,
):
    """構建 run_optimization_loop 所需的全部 mock。

    返回 (patches_list, run_backtest_mock, stop_event)。
    調用方負責進入/退出 patch 上下文。
    """
    ctx_managers = []

    # --- llm_client ---
    mock_llm = MagicMock()
    mock_llm.model_status.available = True
    mock_llm.check_models = AsyncMock()
    ctx_managers.append(patch.object(optimizer, "llm_client", mock_llm))

    # --- backend_client ---
    mock_bc = MagicMock()
    mock_bc.get_latest_trade_date = AsyncMock(return_value="2026-08-20")
    mock_bc.get_market_overview = AsyncMock(return_value={})
    mock_bc.run_backtest = backtest_side_effect
    mock_bc.save_strategy = AsyncMock(return_value={"id": 1})
    ctx_managers.append(patch.object(optimizer, "backend_client", mock_bc))

    # --- _load_best_strategy_from_db：直接返回指定 best_score ---
    default_criteria = {"asOfDate": "2026-01-01", "adjustflag": 3, "excludeSt": True, "maxResults": 50, "sortBy": "score"}
    default_config = {"startDate": "2026-01-01", "endDate": "2026-08-20", "rebalanceInterval": 5, "holdingPeriod": 10, "maxPositions": 5, "initialCapital": 1_000_000, "commissionBps": 3}
    ctx_managers.append(
        patch.object(
            optimizer,
            "_load_best_strategy_from_db",
            AsyncMock(return_value=(default_criteria, default_config, best_score_from_db, None)),
        )
    )

    # --- 各 AI stage：返回簡單 StageResult ---
    strategy_output = '{"reasoning":"test","criteria":{"asOfDate":"2026-01-01","adjustflag":3,"excludeSt":true,"maxResults":50,"sortBy":"score"}}'
    ctx_managers.append(patch.object(optimizer, "_market_news_stage"))
    ctx_managers.append(patch.object(optimizer, "_industry_stage"))
    ctx_managers.append(patch.object(optimizer, "_market_stage"))
    ctx_managers.append(patch.object(optimizer, "_strategy_stage"))
    ctx_managers.append(patch.object(optimizer, "_reflection_stage"))
    ctx_managers.append(patch.object(optimizer, "_prompt_stage"))

    # --- judge ---
    ctx_managers.append(patch.object(optimizer, "_judge", MagicMock()))

    # --- RAG 關閉 ---
    ctx_managers.append(patch.object(optimizer, "is_rag_available", MagicMock(return_value=False)))

    # --- 監控 ---
    ctx_managers.append(patch.object(optimizer, "node_monitor", MagicMock()))

    # --- metrics 函數 ---
    ctx_managers.append(patch.object(optimizer, "record_iteration_complete", MagicMock()))
    ctx_managers.append(patch.object(optimizer, "record_json_failure", MagicMock()))
    ctx_managers.append(patch.object(optimizer, "record_rag_operation", MagicMock()))

    # --- state.restore / checkpoint ---
    ctx_managers.append(patch.object(optimizer.state, "restore", MagicMock(return_value=False)))
    ctx_managers.append(patch.object(optimizer.state, "checkpoint", MagicMock()))

    return ctx_managers, mock_bc, default_criteria, default_config


class TestMultiWindowFlagInLoop:
    """測試 multi_window_backtest 開關在主循環中的行為。"""

    def test_single_window_when_disabled(self, reset_state, monkeypatch):
        """multi_window_backtest=false 時每輪只調用 1 次 run_backtest（保持兼容）。"""
        from app.core.config import settings as real_settings

        monkeypatch.setattr(real_settings, "multi_window_backtest", False)
        monkeypatch.setattr(real_settings, "max_stagnant_iterations", 0)
        monkeypatch.setattr(real_settings, "optimization_interval", 0)

        call_count = 0

        async def fake_run_backtest(criteria, config):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                optimizer._stop_event.set()
            return {"statistics": {"totalReturn": 10, "maxDrawdown": 5, "sharpe": 0}, "logLines": []}

        ctx_list, mock_bc, _, _ = _setup_loop_mocks(fake_run_backtest)
        # 設置 stage.run 為 AsyncMock
        for stage_attr in ("_market_news_stage", "_industry_stage", "_market_stage", "_strategy_stage", "_reflection_stage", "_prompt_stage"):
            pass

        for cm in ctx_list:
            cm.__enter__()

        try:
            # 設置 stage.run
            optimizer._market_news_stage.run = AsyncMock(return_value=_make_stage_result("news"))
            optimizer._industry_stage.run = AsyncMock(return_value=_make_stage_result("industry"))
            optimizer._market_stage.run = AsyncMock(return_value=_make_stage_result("market"))
            optimizer._strategy_stage.run = AsyncMock(return_value=_make_stage_result('{"reasoning":"test"}', "strategy"))
            optimizer._reflection_stage.run = AsyncMock(return_value=_make_stage_result("reflection"))
            optimizer._prompt_stage.run = AsyncMock(return_value=_make_stage_result("prompt"))

            asyncio.run(optimizer.run_optimization_loop())
        finally:
            for cm in ctx_list:
                cm.__exit__(None, None, None)

        assert call_count == 1, f"單窗口模式每輪應只調用 1 次 run_backtest，實際 {call_count}"

    def test_three_calls_when_enabled(self, reset_state, monkeypatch):
        """multi_window_backtest=true 時每輪調用 3 次 run_backtest（3 個窗口）。"""
        from app.core.config import settings as real_settings

        monkeypatch.setattr(real_settings, "multi_window_backtest", True)
        monkeypatch.setattr(real_settings, "max_stagnant_iterations", 0)
        monkeypatch.setattr(real_settings, "optimization_interval", 0)

        call_count = 0

        async def fake_run_backtest(criteria, config):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                optimizer._stop_event.set()
            return {"statistics": {"totalReturn": 10, "maxDrawdown": 5, "sharpe": 0}, "logLines": []}

        ctx_list, _, _, _ = _setup_loop_mocks(fake_run_backtest)

        for cm in ctx_list:
            cm.__enter__()

        try:
            optimizer._market_news_stage.run = AsyncMock(return_value=_make_stage_result("news"))
            optimizer._industry_stage.run = AsyncMock(return_value=_make_stage_result("industry"))
            optimizer._market_stage.run = AsyncMock(return_value=_make_stage_result("market"))
            optimizer._strategy_stage.run = AsyncMock(return_value=_make_stage_result('{"reasoning":"test"}', "strategy"))
            optimizer._reflection_stage.run = AsyncMock(return_value=_make_stage_result("reflection"))
            optimizer._prompt_stage.run = AsyncMock(return_value=_make_stage_result("prompt"))

            asyncio.run(optimizer.run_optimization_loop())
        finally:
            for cm in ctx_list:
                cm.__exit__(None, None, None)

        assert call_count == 3, f"多窗口模式每輪應調用 3 次 run_backtest，實際 {call_count}"

    def test_weighted_score_recorded_when_enabled(self, reset_state, monkeypatch):
        """多窗口模式下，記錄的 composite_score 應為加權平均值（非單窗口值）。"""
        from app.core.config import settings as real_settings

        monkeypatch.setattr(real_settings, "multi_window_backtest", True)
        monkeypatch.setattr(real_settings, "max_stagnant_iterations", 0)
        monkeypatch.setattr(real_settings, "optimization_interval", 0)

        # 3 個窗口分別評分 60/50/40 → 加權 53
        window_scores = [60.0, 50.0, 40.0]
        idx = 0

        async def fake_run_backtest(criteria, config):
            nonlocal idx
            stats = _stats_for_score(window_scores[idx])
            idx += 1
            if idx >= 3:
                optimizer._stop_event.set()
            return {"statistics": stats, "logLines": []}

        ctx_list, _, _, _ = _setup_loop_mocks(fake_run_backtest)

        for cm in ctx_list:
            cm.__enter__()

        try:
            optimizer._market_news_stage.run = AsyncMock(return_value=_make_stage_result("news"))
            optimizer._industry_stage.run = AsyncMock(return_value=_make_stage_result("industry"))
            optimizer._market_stage.run = AsyncMock(return_value=_make_stage_result("market"))
            optimizer._strategy_stage.run = AsyncMock(return_value=_make_stage_result('{"reasoning":"test"}', "strategy"))
            optimizer._reflection_stage.run = AsyncMock(return_value=_make_stage_result("reflection"))
            optimizer._prompt_stage.run = AsyncMock(return_value=_make_stage_result("prompt"))

            asyncio.run(optimizer.run_optimization_loop())
        finally:
            for cm in ctx_list:
                cm.__exit__(None, None, None)

        # 第一輪迭代結果的評分應為加權平均 53（容忍 compute_composite_score 的浮點誤差）
        assert len(reset_state.iterations) >= 1
        recorded = reset_state.iterations[0].composite_score
        assert recorded == pytest.approx(53.0, abs=0.5)


class TestStagnantTermination:
    """測試 max_stagnant_iterations 無進展終止邏輯。"""

    def test_no_limit_when_zero(self, reset_state, monkeypatch):
        """max_stagnant_iterations=0 時不限制，連續低分繼續迭代。"""
        from app.core.config import settings as real_settings

        monkeypatch.setattr(real_settings, "multi_window_backtest", False)
        monkeypatch.setattr(real_settings, "max_stagnant_iterations", 0)
        monkeypatch.setattr(real_settings, "optimization_interval", 0)

        # best_score 從 DB 載入為 50；每輪回測評分也是 50（Δscore=0 < 1，無進展）
        call_count = 0

        async def fake_run_backtest(criteria, config):
            nonlocal call_count
            call_count += 1
            # 跑 5 輪後手動停止，驗證未因無進展提前停止
            if call_count >= 5:
                optimizer._stop_event.set()
            return {"statistics": {"totalReturn": 10, "maxDrawdown": 5, "sharpe": 0}, "logLines": []}

        ctx_list, _, _, _ = _setup_loop_mocks(fake_run_backtest, best_score_from_db=50.0)

        for cm in ctx_list:
            cm.__enter__()

        try:
            optimizer._market_news_stage.run = AsyncMock(return_value=_make_stage_result("news"))
            optimizer._industry_stage.run = AsyncMock(return_value=_make_stage_result("industry"))
            optimizer._market_stage.run = AsyncMock(return_value=_make_stage_result("market"))
            optimizer._strategy_stage.run = AsyncMock(return_value=_make_stage_result('{"reasoning":"test"}', "strategy"))
            optimizer._reflection_stage.run = AsyncMock(return_value=_make_stage_result("reflection"))
            optimizer._prompt_stage.run = AsyncMock(return_value=_make_stage_result("prompt"))

            asyncio.run(optimizer.run_optimization_loop())
        finally:
            for cm in ctx_list:
                cm.__exit__(None, None, None)

        # 應跑滿 5 輪（未被無進展終止）
        assert call_count == 5, f"max_stagnant=0 不應提前停止，應跑滿 5 輪，實際 {call_count}"
        assert reset_state.current_iteration == 5

    def test_stops_after_three_stagnant(self, reset_state, monkeypatch):
        """max_stagnant_iterations=3 時，連續 3 輪 Δscore<1 自動停止。"""
        from app.core.config import settings as real_settings

        monkeypatch.setattr(real_settings, "multi_window_backtest", False)
        monkeypatch.setattr(real_settings, "max_stagnant_iterations", 3)
        monkeypatch.setattr(real_settings, "optimization_interval", 0)

        call_count = 0

        async def fake_run_backtest(criteria, config):
            nonlocal call_count
            call_count += 1
            # 每輪評分 50，best_score 從 DB 載入為 50 → Δscore=0 < 1（無進展）
            return {"statistics": {"totalReturn": 10, "maxDrawdown": 5, "sharpe": 0}, "logLines": []}

        ctx_list, _, _, _ = _setup_loop_mocks(fake_run_backtest, best_score_from_db=50.0)

        for cm in ctx_list:
            cm.__enter__()

        try:
            optimizer._market_news_stage.run = AsyncMock(return_value=_make_stage_result("news"))
            optimizer._industry_stage.run = AsyncMock(return_value=_make_stage_result("industry"))
            optimizer._market_stage.run = AsyncMock(return_value=_make_stage_result("market"))
            optimizer._strategy_stage.run = AsyncMock(return_value=_make_stage_result('{"reasoning":"test"}', "strategy"))
            optimizer._reflection_stage.run = AsyncMock(return_value=_make_stage_result("reflection"))
            optimizer._prompt_stage.run = AsyncMock(return_value=_make_stage_result("prompt"))

            asyncio.run(optimizer.run_optimization_loop())
        finally:
            for cm in ctx_list:
                cm.__exit__(None, None, None)

        # 連續 3 輪無進展後停止 → 應剛好跑 3 輪
        assert call_count == 3, f"連續 3 輪無進展應自動停止，應跑 3 輪，實際 {call_count}"
        assert reset_state.current_iteration == 3
        assert "無進展" in reset_state.status_message or "停止" in reset_state.status_message

    def test_resets_on_improvement(self, reset_state, monkeypatch):
        """有實質進展時應重置計數器，不提前停止。"""
        from app.core.config import settings as real_settings

        monkeypatch.setattr(real_settings, "multi_window_backtest", False)
        monkeypatch.setattr(real_settings, "max_stagnant_iterations", 3)
        monkeypatch.setattr(real_settings, "optimization_interval", 0)

        # best_score 從 DB=50。輪次評分序列：50(無進展), 52(進展≥1，重置), 50(無), 50(無), 50(無→停止)
        # 即第 1 輪無進展(count=1)，第 2 輪進展(count=0)，第 3-5 輪無進展(count=3→停止)
        score_sequence = [50.0, 52.0, 50.0, 50.0, 50.0]
        call_count = 0

        async def fake_run_backtest(criteria, config):
            nonlocal call_count
            idx = call_count
            call_count += 1
            stats = _stats_for_score(score_sequence[idx])
            return {"statistics": stats, "logLines": []}

        ctx_list, _, _, _ = _setup_loop_mocks(fake_run_backtest, best_score_from_db=50.0)

        for cm in ctx_list:
            cm.__enter__()

        try:
            optimizer._market_news_stage.run = AsyncMock(return_value=_make_stage_result("news"))
            optimizer._industry_stage.run = AsyncMock(return_value=_make_stage_result("industry"))
            optimizer._market_stage.run = AsyncMock(return_value=_make_stage_result("market"))
            optimizer._strategy_stage.run = AsyncMock(return_value=_make_stage_result('{"reasoning":"test"}', "strategy"))
            optimizer._reflection_stage.run = AsyncMock(return_value=_make_stage_result("reflection"))
            optimizer._prompt_stage.run = AsyncMock(return_value=_make_stage_result("prompt"))

            asyncio.run(optimizer.run_optimization_loop())
        finally:
            for cm in ctx_list:
                cm.__exit__(None, None, None)

        # 第 2 輪進展重置計數器，第 3-5 輪連續 3 次無進展 → 跑 5 輪停止
        assert call_count == 5, f"進展應重置計數器，應跑 5 輪後停止，實際 {call_count}"
