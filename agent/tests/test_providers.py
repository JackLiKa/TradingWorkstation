"""測試多模型路由架構 — providers 註冊表 + 路由邏輯。"""
import os
import pytest

from app.core.providers import (
    PROVIDERS,
    STAGE_DEFAULT_PROVIDERS,
    get_provider_info,
    get_all_provider_ids,
    get_default_provider_for_stage,
    is_openai_compatible,
    get_api_key,
)


class TestProviderRegistry:
    """測試供應商註冊表。"""

    def test_all_providers_defined(self):
        """應該有 7 個供應商。"""
        expected = {
            "deepseek-pro", "deepseek-flash",
            "glm-5.2", "glm-flash",
            "qwen", "qoder", "devin",
        }
        assert set(PROVIDERS.keys()) == expected

    def test_provider_info_complete(self):
        """每個供應商應該有完整元數據。"""
        for pid, info in PROVIDERS.items():
            assert info.provider == pid
            assert info.display_name
            assert info.model_id
            assert info.api_key_env
            assert info.tags
            assert info.description

    def test_free_providers(self):
        """免費供應商應該標記 is_free=True。"""
        free = ["glm-flash", "qoder", "devin"]
        for pid in free:
            assert PROVIDERS[pid].is_free is True

    def test_paid_providers(self):
        """付費供應商應該標記 is_free=False 並有價格。"""
        paid = ["deepseek-pro", "deepseek-flash", "glm-5.2", "qwen"]
        for pid in paid:
            assert PROVIDERS[pid].is_free is False
            assert PROVIDERS[pid].input_price > 0
            assert PROVIDERS[pid].output_price > 0

    def test_json_mode_support(self):
        """需要 JSON 的供應商應該支持 json_mode。"""
        json_providers = ["deepseek-pro", "deepseek-flash", "glm-5.2", "glm-flash", "qwen"]
        for pid in json_providers:
            assert PROVIDERS[pid].supports_json_mode is True

    def test_openai_compatible_providers(self):
        """OpenAI-compatible 供應商應該有 base_url。"""
        compatible = ["deepseek-pro", "deepseek-flash", "glm-5.2", "glm-flash", "qwen"]
        for pid in compatible:
            assert is_openai_compatible(pid) is True
            assert PROVIDERS[pid].base_url

    def test_non_openai_providers(self):
        """Qoder 和 Devin 不走 OpenAI API。"""
        assert is_openai_compatible("qoder") is False
        assert is_openai_compatible("devin") is False

    def test_get_provider_info(self):
        info = get_provider_info("deepseek-pro")
        assert info is not None
        assert info.display_name == "DeepSeek V4-Pro"

    def test_get_provider_info_unknown(self):
        assert get_provider_info("unknown") is None

    def test_get_all_provider_ids(self):
        ids = get_all_provider_ids()
        assert len(ids) == 7
        assert "deepseek-pro" in ids


class TestStageRouting:
    """測試階段默認路由。"""

    def test_all_stages_have_default(self):
        """所有核心階段都應該有默認供應商。"""
        required = [
            "market_news", "industry_analysis", "market_analysis",
            "strategy_generation", "backtest_reflection", "prompt_generation",
            "judge", "monitor",
        ]
        for stage in required:
            assert stage in STAGE_DEFAULT_PROVIDERS, f"{stage} 缺少默認供應商"

    def test_strategy_generation_uses_deepseek_pro(self):
        """AI 2 策略生成應該用 DeepSeek V4-Pro（推理最強）。"""
        assert STAGE_DEFAULT_PROVIDERS["strategy_generation"] == "deepseek-pro"

    def test_judge_uses_free_provider(self):
        """Judge 應該用免費供應商。"""
        provider = STAGE_DEFAULT_PROVIDERS["judge"]
        assert PROVIDERS[provider].is_free is True

    def test_market_news_uses_qwen(self):
        """AI 0 行情新聞應該用 Qwen（中文金融最佳）。"""
        assert STAGE_DEFAULT_PROVIDERS["market_news"] == "qwen"

    def test_industry_analysis_uses_glm(self):
        """AI 0.5 行業分析應該用 GLM-5.2（JSON 最穩定）。"""
        assert STAGE_DEFAULT_PROVIDERS["industry_analysis"] == "glm-5.2"

    def test_get_default_for_stage(self):
        assert get_default_provider_for_stage("strategy_generation") == "deepseek-pro"
        assert get_default_provider_for_stage("unknown_stage") == ""


class TestApiKeyRetrieval:
    """測試 API key 獲取。"""

    def test_get_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-123")
        assert get_api_key("deepseek-pro") == "test-key-123"
        assert get_api_key("deepseek-flash") == "test-key-123"  # 共用同一個 key

    def test_get_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("GLM_API_KEY", raising=False)
        assert get_api_key("glm-5.2") == ""

    def test_get_api_key_unknown_provider(self):
        assert get_api_key("unknown") == ""
