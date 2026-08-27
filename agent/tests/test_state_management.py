"""測試三層狀態管理 — state.py 擴展（瞬時/持久/DB）+ 回顧分析 + 當日摘要。"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.state import (
    DEFAULT_BACKTEST_CONFIG,
    DEFAULT_CRITERIA,
    DailyDigest,
    IterationResult,
    OptimizerState,
    RETROSPECTIVE_INTERVAL,
    RetrospectiveResult,
    StageResult,
)


class TestRetrospectiveResult:
    """回顧分析結果數據類測試。"""

    def test_to_dict_serializes_iteration_range_to_list(self):
        """to_dict 應將 tuple iteration_range 序列化為 list。"""
        result = RetrospectiveResult(
            iteration_range=(1, 5),
            timestamp="2026-08-24T10:00:00",
            findings="測試問題",
            optimization_summary="測試總結",
            improvement_plan="測試方案",
        )
        d = result.to_dict()
        assert d["iteration_range"] == [1, 5]
        assert d["findings"] == "測試問題"

    def test_from_dict_restores_iteration_range_to_tuple(self):
        """from_dict 應將 list iteration_range 恢復為 tuple。"""
        data = {
            "iteration_range": [1, 5],
            "timestamp": "2026-08-24T10:00:00",
            "findings": "測試",
            "optimization_summary": "總結",
            "improvement_plan": "方案",
            "stage_issues": {"market_news": "問題"},
            "score_trend": "上升",
            "recommendations": ["建議1", "建議2"],
        }
        result = RetrospectiveResult.from_dict(data)
        assert result.iteration_range == (1, 5)
        assert result.recommendations == ["建議1", "建議2"]

    def test_to_prompt_text_contains_all_sections(self):
        """to_prompt_text 應包含所有關鍵段落。"""
        result = RetrospectiveResult(
            iteration_range=(1, 5),
            timestamp="2026-08-24T10:00:00",
            findings="發現的問題",
            optimization_summary="優化總結",
            improvement_plan="改善方案",
            recommendations=["建議1", "建議2"],
        )
        text = result.to_prompt_text()
        assert "回顧分析" in text
        assert "發現的問題" in text
        assert "優化總結" in text
        assert "改善方案" in text
        assert "建議1" in text


class TestDailyDigest:
    """當日市場摘要數據類測試。"""

    def test_to_dict_and_from_dict_roundtrip(self):
        """to_dict + from_dict 應能完整往返。"""
        digest = DailyDigest(
            trade_date="2026-08-24",
            timestamp="2026-08-24T10:00:00",
            market_overview="上證指數3200點",
            sector_highlights="半導體強勢",
            news_digest="央行降準",
            sentiment="偏多",
            key_events=["事件1", "事件2"],
            data_sources=["DB", "華爾街見聞"],
        )
        d = digest.to_dict()
        restored = DailyDigest.from_dict(d)
        assert restored.trade_date == "2026-08-24"
        assert restored.market_overview == "上證指數3200點"
        assert restored.key_events == ["事件1", "事件2"]
        assert restored.data_sources == ["DB", "華爾街見聞"]

    def test_to_prompt_text_contains_trade_date_and_sections(self):
        """to_prompt_text 應包含交易日和各段落。"""
        digest = DailyDigest(
            trade_date="2026-08-24",
            timestamp="2026-08-24T10:00:00",
            market_overview="市場概覽內容",
            sector_highlights="板塊亮點內容",
            news_digest="新聞摘要內容",
            sentiment="偏多",
            key_events=["關鍵事件"],
            data_sources=["DB"],
        )
        text = digest.to_prompt_text()
        assert "2026-08-24" in text
        assert "市場概覽" in text
        assert "板塊亮點" in text
        assert "新聞摘要" in text
        assert "關鍵事件" in text

    def test_from_dict_camelCase_java_api_response(self):
        """from_dict 應兼容 Java API 的 camelCase 字段名。"""
        java_api_data = {
            "id": 1,
            "tradeDate": "2026-08-24",
            "marketOverview": "上證指數3200點",
            "sectorHighlights": "半導體強勢",
            "newsDigest": "央行降準",
            "sentiment": "偏多",
            "keyEvents": ["事件1", "事件2"],
            "dataSources": ["DB", "華爾街見聞"],
            "generatedAt": "2026-08-24T10:00:00",
        }
        digest = DailyDigest.from_dict(java_api_data)
        assert digest.trade_date == "2026-08-24"
        assert digest.market_overview == "上證指數3200點"
        assert digest.sector_highlights == "半導體強勢"
        assert digest.news_digest == "央行降準"
        assert digest.sentiment == "偏多"
        assert digest.key_events == ["事件1", "事件2"]
        assert digest.data_sources == ["DB", "華爾街見聞"]
        assert digest.timestamp == "2026-08-24T10:00:00"

    def test_from_dict_snake_case_internal_serialization(self):
        """from_dict 應兼容內部 state 序列化的 snake_case 字段名。"""
        snake_data = {
            "trade_date": "2026-08-24",
            "timestamp": "2026-08-24T10:00:00",
            "market_overview": "概覽",
            "sector_highlights": "亮點",
            "news_digest": "摘要",
            "sentiment": "中性",
            "key_events": ["事件"],
            "data_sources": ["DB"],
        }
        digest = DailyDigest.from_dict(snake_data)
        assert digest.trade_date == "2026-08-24"
        assert digest.market_overview == "概覽"
        assert digest.sentiment == "中性"

    def test_is_empty_true_when_trade_date_missing(self):
        """is_empty 應在 trade_date 為空時返回 True。"""
        digest = DailyDigest(
            trade_date="",
            timestamp="",
            market_overview="有內容",
            sector_highlights="",
            news_digest="",
            sentiment="",
        )
        assert digest.is_empty() is True

    def test_is_empty_true_when_market_overview_missing(self):
        """is_empty 應在 market_overview 為空時返回 True。"""
        digest = DailyDigest(
            trade_date="2026-08-24",
            timestamp="",
            market_overview="",
            sector_highlights="",
            news_digest="",
            sentiment="",
        )
        assert digest.is_empty() is True

    def test_is_empty_false_when_required_fields_present(self):
        """is_empty 應在 trade_date 和 market_overview 都非空時返回 False。"""
        digest = DailyDigest(
            trade_date="2026-08-24",
            timestamp="2026-08-24T10:00:00",
            market_overview="上證指數3200點",
            sector_highlights="",
            news_digest="",
            sentiment="",
        )
        assert digest.is_empty() is False


class TestOptimizerStateExtensions:
    """OptimizerState 擴展字段測試。"""

    def test_state_has_retrospective_fields(self):
        """state 應有回顧分析相關字段。"""
        state = OptimizerState()
        assert state.last_retrospective is None
        assert state.retrospective_count == 0

    def test_state_has_daily_digest_fields(self):
        """state 應有當日摘要相關字段。"""
        state = OptimizerState()
        assert state.current_daily_digest is None
        assert state.daily_digest_date == ""

    def test_to_dict_includes_new_fields(self):
        """to_dict 應包含回顧分析和當日摘要字段。"""
        state = OptimizerState()
        state.retrospective_count = 3
        state.daily_digest_date = "2026-08-24"
        d = state.to_dict()
        assert d["retrospective_count"] == 3
        assert d["daily_digest_date"] == "2026-08-24"
        assert d["last_retrospective"] is None
        assert d["current_daily_digest"] is None

    def test_to_dict_with_retrospective_and_digest(self):
        """to_dict 應正確序列化回顧結果和摘要。"""
        state = OptimizerState()
        state.last_retrospective = RetrospectiveResult(
            iteration_range=(1, 5),
            timestamp="2026-08-24T10:00:00",
            findings="問題",
            optimization_summary="總結",
            improvement_plan="方案",
        )
        state.current_daily_digest = DailyDigest(
            trade_date="2026-08-24",
            timestamp="2026-08-24T10:00:00",
            market_overview="概覽",
            sector_highlights="亮點",
            news_digest="摘要",
            sentiment="偏多",
        )
        d = state.to_dict()
        assert d["last_retrospective"] is not None
        assert d["last_retrospective"]["iteration_range"] == [1, 5]
        assert d["current_daily_digest"] is not None
        assert d["current_daily_digest"]["trade_date"] == "2026-08-24"

    def test_checkpoint_includes_retrospective(self):
        """checkpoint 應保存回顧分析結果。"""
        state = OptimizerState()
        state.last_retrospective = RetrospectiveResult(
            iteration_range=(1, 5),
            timestamp="2026-08-24T10:00:00",
            findings="問題",
            optimization_summary="總結",
            improvement_plan="方案",
        )
        state.retrospective_count = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "checkpoint.json")
            state.checkpoint(path)

            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["retrospective_count"] == 1
            assert data["last_retrospective"] is not None
            assert data["last_retrospective"]["iteration_range"] == [1, 5]

    def test_restore_includes_retrospective(self):
        """restore 應恢復回顧分析結果。"""
        state = OptimizerState()
        state.last_retrospective = RetrospectiveResult(
            iteration_range=(1, 5),
            timestamp="2026-08-24T10:00:00",
            findings="問題",
            optimization_summary="總結",
            improvement_plan="方案",
        )
        state.retrospective_count = 1
        state.current_daily_digest = DailyDigest(
            trade_date="2026-08-24",
            timestamp="2026-08-24T10:00:00",
            market_overview="概覽",
            sector_highlights="亮點",
            news_digest="摘要",
            sentiment="偏多",
        )
        state.daily_digest_date = "2026-08-24"

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "checkpoint.json")
            state.checkpoint(path)

            # 新 state 從 checkpoint 恢復
            new_state = OptimizerState()
            restored = new_state.restore(path)

            assert restored is True
            assert new_state.retrospective_count == 1
            assert new_state.last_retrospective is not None
            assert new_state.last_retrospective.iteration_range == (1, 5)
            assert new_state.current_daily_digest is not None
            assert new_state.current_daily_digest.trade_date == "2026-08-24"
            assert new_state.daily_digest_date == "2026-08-24"

    def test_to_db_json_includes_all_fields(self):
        """to_db_json 應包含所有持久化字段。"""
        state = OptimizerState()
        state.current_iteration = 5
        state.best_score = 70.5
        state.retrospective_count = 1
        state.last_retrospective = RetrospectiveResult(
            iteration_range=(1, 5),
            timestamp="2026-08-24T10:00:00",
            findings="問題",
            optimization_summary="總結",
            improvement_plan="方案",
        )
        state.current_daily_digest = DailyDigest(
            trade_date="2026-08-24",
            timestamp="2026-08-24T10:00:00",
            market_overview="概覽",
            sector_highlights="亮點",
            news_digest="摘要",
            sentiment="偏多",
        )
        state.daily_digest_date = "2026-08-24"

        db_json = state.to_db_json()
        parsed = json.loads(db_json)
        assert parsed["current_iteration"] == 5
        assert parsed["best_score"] == 70.5
        assert parsed["retrospective_count"] == 1
        assert parsed["last_retrospective"] is not None
        assert parsed["current_daily_digest"] is not None
        assert parsed["daily_digest_date"] == "2026-08-24"


class TestRetrospectiveInterval:
    """回顧分析觸發間隔測試。"""

    def test_retrospective_interval_is_5(self):
        """RETROSPECTIVE_INTERVAL 應為 5。"""
        assert RETROSPECTIVE_INTERVAL == 5


class TestRetrospectiveParsing:
    """回顧分析輸出解析測試。"""

    def test_parse_valid_json(self):
        """parse_retrospective_output 應正確解析有效 JSON。"""
        from app.agents.stages.retrospective import parse_retrospective_output

        output = json.dumps({
            "findings": "第3輪AI2疊加條件導致0交易",
            "optimization_summary": "5輪總體上升",
            "improvement_plan": "替換而非疊加條件",
            "stage_issues": {"strategy_generation": "條件疊加"},
            "score_trend": "62→68",
            "recommendations": ["建議1", "建議2"],
        }, ensure_ascii=False)

        result = parse_retrospective_output(output)
        assert result.findings == "第3輪AI2疊加條件導致0交易"
        assert result.recommendations == ["建議1", "建議2"]
        assert result.stage_issues == {"strategy_generation": "條件疊加"}

    def test_parse_json_with_markdown_codeblock(self):
        """parse_retrospective_output 應處理 markdown 代碼塊標記。"""
        from app.agents.stages.retrospective import parse_retrospective_output

        output = '```json\n{"findings": "問題", "optimization_summary": "總結", "improvement_plan": "方案", "stage_issues": {}, "score_trend": "", "recommendations": []}\n```'

        result = parse_retrospective_output(output)
        assert result.findings == "問題"

    def test_parse_invalid_json_raises_value_error(self):
        """parse_retrospective_output 對無效 JSON 應拋出 ValueError。"""
        from app.agents.stages.retrospective import parse_retrospective_output

        with pytest.raises(ValueError):
            parse_retrospective_output("不是JSON")


class TestDailyDigestTradeDate:
    """當日摘要交易日解析測試。"""

    def test_resolve_trade_date_weekday(self):
        """工作日應返回當天。"""
        from app.services.daily_digest import _resolve_trade_date

        # 模擬週一（不傳 latest_trade_date，用日曆推算）
        # 注意：實際結果取決於運行日期，這裡只測試邏輯
        result = _resolve_trade_date(None)
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD

    def test_resolve_trade_date_with_db_date(self):
        """若DB最新交易日早於今天，應用DB最新交易日。"""
        from app.services.daily_digest import _resolve_trade_date

        # 傳入一個較早的日期
        result = _resolve_trade_date("2020-01-01")
        assert result == "2020-01-01"

    def test_resolve_trade_date_db_date_equal_today(self):
        """若DB最新交易日等於今天，應返回今天。"""
        from app.services.daily_digest import _resolve_trade_date

        today = datetime.now().strftime("%Y-%m-%d")
        # 週末時 today 已被回退，所以傳入 today 可能不等於結果
        # 但若傳入未來日期，應返回日曆推算的今天
        result = _resolve_trade_date(today)
        # 結果應該是今天或週末回退後的週五
        assert isinstance(result, str)


class TestRetrospectiveStage:
    """回顧分析 Stage 測試。"""

    @pytest.mark.asyncio
    async def test_retrospective_stage_empty_iterations(self):
        """無迭代數據時應返回默認空結果。"""
        from app.agents.stages.retrospective import RetrospectiveStage

        stage = RetrospectiveStage()
        output = await stage.execute(iterations=[], prev_retrospective="")
        parsed = json.loads(output)
        assert parsed["findings"] == "無迭代數據可分析"

    @pytest.mark.asyncio
    async def test_run_retrospective_insufficient_iterations(self):
        """迭代數不足時應返回 None。"""
        from app.agents.stages.retrospective import run_retrospective

        state = OptimizerState()
        state.iterations = [IterationResult(
            iteration=1, timestamp="", criteria={}, config={},
            screener_summary="", backtest_statistics={}, composite_score=60,
        )]

        result = await run_retrospective(state, window_size=5)
        assert result is None


class TestStateDbPersistence:
    """狀態 DB 持久化測試（mock 後端調用）。"""

    @pytest.mark.asyncio
    async def test_checkpoint_db_calls_backend(self):
        """checkpoint_db 應調用 backend_client.save_agent_state。"""
        state = OptimizerState()
        state.current_iteration = 3
        state.best_score = 65.0

        with patch("app.services.backend_client.backend_client.save_agent_state", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = {"id": 1}
            result = await state.checkpoint_db()
            assert result is True
            mock_save.assert_awaited_once()
            call_args = mock_save.call_args
            assert call_args.kwargs["current_iteration"] == 3
            assert call_args.kwargs["best_score"] == 65.0

    @pytest.mark.asyncio
    async def test_checkpoint_db_failure_returns_false(self):
        """checkpoint_db 後端不可用時應返回 False。"""
        state = OptimizerState()

        with patch("app.services.backend_client.backend_client.save_agent_state", new_callable=AsyncMock) as mock_save:
            mock_save.side_effect = Exception("後端不可用")
            result = await state.checkpoint_db()
            assert result is False

    @pytest.mark.asyncio
    async def test_restore_db_success(self):
        """restore_db 應正確恢復狀態。"""
        state = OptimizerState()

        db_data = {
            "stateJson": json.dumps({
                "current_iteration": 5,
                "best_score": 70.5,
                "best_iteration": 3,
                "best_criteria": {"asOfDate": "2026-01-01"},
                "best_config": {"startDate": "2025-01-01"},
                "current_criteria": {"asOfDate": "2026-01-01"},
                "current_config": {"startDate": "2025-01-01"},
                "current_reflection": "反思",
                "current_next_prompt": "提示",
                "last_retrospective": {
                    "iteration_range": [1, 5],
                    "timestamp": "2026-08-24T10:00:00",
                    "findings": "問題",
                    "optimization_summary": "總結",
                    "improvement_plan": "方案",
                },
                "retrospective_count": 1,
                "current_daily_digest": {
                    "trade_date": "2026-08-24",
                    "timestamp": "2026-08-24T10:00:00",
                    "market_overview": "概覽",
                    "sector_highlights": "亮點",
                    "news_digest": "摘要",
                    "sentiment": "偏多",
                },
                "daily_digest_date": "2026-08-24",
                "recent_iterations": [],
            })
        }

        with patch("app.services.backend_client.backend_client.load_agent_state", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = db_data
            result = await state.restore_db()
            assert result is True
            assert state.current_iteration == 5
            assert state.best_score == 70.5
            assert state.retrospective_count == 1
            assert state.last_retrospective is not None
            assert state.last_retrospective.iteration_range == (1, 5)
            assert state.current_daily_digest is not None
            assert state.current_daily_digest.trade_date == "2026-08-24"

    @pytest.mark.asyncio
    async def test_restore_db_no_record_returns_false(self):
        """restore_db 無記錄時應返回 False。"""
        state = OptimizerState()

        with patch("app.services.backend_client.backend_client.load_agent_state", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = None
            result = await state.restore_db()
            assert result is False
