"""測試 RAG 經驗存儲 — 格式化和降級。"""
import pytest

from app.services.experience_store import (
    format_experiences_for_prompt,
    is_rag_available,
    get_rag_status,
)


class TestFormatExperiences:
    """測試經驗格式化。"""

    def test_empty_experiences(self):
        """空經驗列表應該返回空字符串。"""
        result = format_experiences_for_prompt([])
        assert result == ""

    def test_single_experience(self):
        """單條經驗格式化。"""
        experiences = [{
            "iteration": 3,
            "similarity": 0.85,
            "composite_score": 68.5,
            "market_context": "震盪上行，波動率18%",
            "criteria": {"minTurn": 1.5, "minReturn20": 3.0},
            "stats": {"totalReturn": 5.2, "maxDrawdown": 6.8, "sharpe": 1.05},
            "reflection": "回撤偏高，建議增加止損",
        }]
        result = format_experiences_for_prompt(experiences)
        assert "第3輪" in result
        assert "相似度0.85" in result
        assert "minTurn" in result
        assert "收益5.2" in result
        assert "回撤偏高" in result
        assert "歷史相似經驗" in result

    def test_multiple_experiences(self):
        """多條經驗都應該被格式化。"""
        experiences = [
            {
                "iteration": 1,
                "similarity": 0.9,
                "composite_score": 70.0,
                "market_context": "牛市",
                "criteria": {"minTurn": 2.0},
                "stats": {"totalReturn": 10.0, "maxDrawdown": 5.0, "sharpe": 1.5},
                "reflection": "表現良好",
            },
            {
                "iteration": 2,
                "similarity": 0.8,
                "composite_score": 65.0,
                "market_context": "震盪",
                "criteria": {"minTurn": 1.0},
                "stats": {"totalReturn": 3.0, "maxDrawdown": 8.0, "sharpe": 0.5},
                "reflection": "回撤偏高",
            },
        ]
        result = format_experiences_for_prompt(experiences)
        assert "第1輪" in result
        assert "第2輪" in result
        assert "經驗1" in result
        assert "經驗2" in result

    def test_empty_fields_handled(self):
        """空字段不應該導致格式化失敗。"""
        experiences = [{
            "iteration": 1,
            "similarity": 0.5,
            "composite_score": 0,
            "market_context": "",
            "criteria": {},
            "stats": {},
            "reflection": "",
        }]
        result = format_experiences_for_prompt(experiences)
        assert "第1輪" in result
        # 不應該崩潰

    def test_long_text_truncated(self):
        """長文本應該被截斷。"""
        long_market = "市場環境" * 500
        long_reflection = "反思" * 500
        experiences = [{
            "iteration": 1,
            "similarity": 0.9,
            "composite_score": 70,
            "market_context": long_market,
            "criteria": {},
            "stats": {},
            "reflection": long_reflection,
        }]
        result = format_experiences_for_prompt(experiences)
        # 市場環境截斷到 150 字
        assert len(result) < len(long_market) + len(long_reflection)


class TestRagAvailability:
    """測試 RAG 可用性檢查。"""

    def test_get_rag_status_structure(self):
        """get_rag_status 應該返回正確結構。"""
        status = get_rag_status()
        assert "available" in status
        assert "milvus_connected" in status
        assert "embedding_model_loaded" in status
        assert "init_error" in status
        assert isinstance(status["available"], bool)

    def test_is_rag_available_returns_bool(self):
        """is_rag_available 應該返回布爾值。"""
        result = is_rag_available()
        assert isinstance(result, bool)
