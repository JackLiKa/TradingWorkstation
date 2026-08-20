"""測試狀態管理 — 持久化、截斷、序列化。"""

import os

from app.agents.state import (
    MAX_IN_MEMORY_ITERATIONS,
    IterationResult,
    OptimizerState,
    StageResult,
)


class TestStageResult:
    """測試階段結果序列化。"""

    def test_to_dict(self):
        sr = StageResult(
            stage_name="market_news",
            output="測試輸出",
            judge_score=85.0,
            judge_passed=True,
            judge_feedback="良好",
            attempts=1,
            duration_ms=500,
        )
        d = sr.to_dict()
        assert d["stage_name"] == "market_news"
        assert d["output"] == "測試輸出"
        assert d["judge_score"] == 85.0
        assert d["judge_passed"] is True

    def test_defaults(self):
        sr = StageResult(stage_name="test", output="x")
        assert sr.judge_score == 0.0
        assert sr.judge_passed is True
        assert sr.attempts == 1
        assert sr.error is None


class TestIterationResult:
    """測試迭代結果。"""

    def test_to_dict(self):
        ir = IterationResult(
            iteration=1,
            timestamp="2026-01-01",
            criteria={"minTurn": 1.5},
            config={"rebalanceInterval": 5},
            screener_summary="命中10隻",
            backtest_statistics={"totalReturn": 5.0},
            composite_score=72.5,
        )
        d = ir.to_dict()
        assert d["iteration"] == 1
        assert d["composite_score"] == 72.5
        assert d["criteria"]["minTurn"] == 1.5

    def test_with_error(self):
        ir = IterationResult(
            iteration=1,
            timestamp="2026-01-01",
            criteria={},
            config={},
            screener_summary="",
            backtest_statistics={},
            composite_score=0,
            error="測試錯誤",
        )
        assert ir.error == "測試錯誤"


class TestOptimizerStatePersistence:
    """測試狀態持久化。"""

    def test_checkpoint_and_restore(self, tmp_path):
        """checkpoint 後 restore 應該恢復關鍵狀態。"""
        s = OptimizerState()
        s.current_iteration = 5
        s.best_score = 72.5
        s.best_criteria = {"minTurn": 1.5, "minReturn20": 3.0}
        s.current_reflection = "需要增加止損"

        path = str(tmp_path / "checkpoint.json")
        saved_path = s.checkpoint(path)
        assert saved_path == path
        assert os.path.exists(path)

        s2 = OptimizerState()
        restored = s2.restore(path)
        assert restored is True
        assert s2.current_iteration == 5
        assert s2.best_score == 72.5
        assert s2.best_criteria["minTurn"] == 1.5
        assert s2.current_reflection == "需要增加止損"

    def test_restore_nonexistent(self):
        """restore 不存在的文件應該返回 False。"""
        s = OptimizerState()
        result = s.restore("/nonexistent/path/checkpoint.json")
        assert result is False

    def test_checkpoint_creates_directory(self, tmp_path):
        """checkpoint 應該自動創建目錄。"""
        s = OptimizerState()
        path = str(tmp_path / "subdir" / "checkpoint.json")
        saved = s.checkpoint(path)
        assert saved == path
        assert os.path.exists(path)


class TestOptimizerStateTruncation:
    """測試內存截斷。"""

    def test_add_iteration_truncation(self):
        """超過上限時應該截斷舊記錄。"""
        s = OptimizerState()
        for i in range(MAX_IN_MEMORY_ITERATIONS + 20):
            s.add_iteration(
                IterationResult(
                    iteration=i + 1,
                    timestamp="2026-01-01",
                    criteria={},
                    config={},
                    screener_summary="",
                    backtest_statistics={},
                    composite_score=60.0 + i * 0.1,
                )
            )
        assert len(s.iterations) == MAX_IN_MEMORY_ITERATIONS
        # 保留的應該是最新的
        assert s.iterations[-1].iteration == MAX_IN_MEMORY_ITERATIONS + 20
        # 最舊的應該被移除
        assert s.iterations[0].iteration == 21  # 1-20 被移除

    def test_add_iteration_no_truncation_under_limit(self):
        """未超過上限時不應截斷。"""
        s = OptimizerState()
        for i in range(10):
            s.add_iteration(
                IterationResult(
                    iteration=i + 1,
                    timestamp="2026-01-01",
                    criteria={},
                    config={},
                    screener_summary="",
                    backtest_statistics={},
                    composite_score=60.0,
                )
            )
        assert len(s.iterations) == 10


class TestOptimizerStateSerialization:
    """測試狀態序列化。"""

    def test_to_dict(self):
        s = OptimizerState()
        s.running = True
        s.current_iteration = 3
        s.best_score = 75.0
        d = s.to_dict()
        assert d["running"] is True
        assert d["current_iteration"] == 3
        assert d["best_score"] == 75.0
        assert "model_status" in d
        assert "available_providers" in d
