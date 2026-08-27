"""測試配置管理和 Prometheus 指標。"""

import pytest

from app.core.config import Settings, settings
from app.core.metrics import (
    inc_counter,
    observe_histogram,
    record_backend_call,
    record_iteration_complete,
    record_llm_call,
    render_prometheus_metrics,
    set_gauge,
)


class TestConfig:
    """測試配置管理。"""

    def test_settings_has_required_fields(self):
        """配置應該包含所有必需字段。"""
        assert hasattr(settings, "devin_api_key")
        assert hasattr(settings, "qoder_personal_access_token")
        assert hasattr(settings, "backend_api_url")
        assert hasattr(settings, "agent_port")
        assert hasattr(settings, "optimization_interval")
        assert hasattr(settings, "rate_limit_backtest")
        assert hasattr(settings, "embedding_model")
        assert hasattr(settings, "environment")
        assert hasattr(settings, "log_level")

    def test_environment_validation(self):
        """環境標識應該驗證。"""
        with pytest.raises(ValueError):
            Settings(environment="invalid")

    def test_log_level_validation(self):
        """日誌級別應該驗證。"""
        with pytest.raises(ValueError):
            Settings(log_level="INVALID")

    def test_is_production(self):
        """is_production 屬性。"""
        s = Settings(environment="production")
        assert s.is_production is True
        s2 = Settings(environment="development")
        assert s2.is_production is False

    def test_validate_for_production(self):
        """生產環境驗證。"""
        s = Settings(
            environment="production",
            devin_api_key="",
            qoder_personal_access_token="",
            backend_api_url="http://localhost:8090",
        )
        errors = s.validate_for_production()
        # 應該有錯誤：無 API key + localhost 後端
        assert len(errors) >= 1

    def test_validate_for_production_ok(self):
        """正常的生產配置應該無錯誤。"""
        s = Settings(
            environment="production",
            devin_api_key="key",
            backend_api_url="http://prod-server:8090/TradingWorkstation",
            optimization_interval=5,
            agent_port=8100,
        )
        errors = s.validate_for_production()
        assert errors == []

    def test_to_dict_hides_secrets(self):
        """to_dict 不應該暴露密鑰明文。"""
        s = Settings(devin_api_key="secret-key-123")
        d = s.to_dict()
        # 不應該包含明文密鑰
        assert "secret-key-123" not in str(d)
        # 但應該顯示是否已設置
        assert d["devin_api_key_set"] is True


class TestMetrics:
    """測試 Prometheus 指標。"""

    def test_inc_counter(self):
        inc_counter("test_counter", {"label": "a"})
        inc_counter("test_counter", {"label": "a"})
        text = render_prometheus_metrics()
        assert "test_counter" in text

    def test_set_gauge(self):
        set_gauge("test_gauge", 42.5, {"name": "x"})
        text = render_prometheus_metrics()
        assert "test_gauge" in text
        assert "42.5" in text

    def test_observe_histogram(self):
        observe_histogram("test_hist", 1.5, {"type": "a"})
        observe_histogram("test_hist", 3.0, {"type": "a"})
        text = render_prometheus_metrics()
        assert "test_hist" in text
        assert "_bucket" in text
        assert "_count" in text
        assert "_sum" in text

    def test_record_iteration_complete(self):
        record_iteration_complete(iteration=5, score=72.5)
        text = render_prometheus_metrics()
        assert "agent_optimization_iterations_total" in text
        assert "agent_optimization_score" in text

    def test_record_llm_call(self):
        record_llm_call("qoder", "qoder-lite", 1.5, fallback=False)
        text = render_prometheus_metrics()
        assert "agent_llm_calls_total" in text
        assert "agent_llm_duration_seconds" in text

    def test_record_backend_call(self):
        record_backend_call("api/backtest", success=True, retried=False)
        record_backend_call("api/backtest", success=False, retried=True)
        text = render_prometheus_metrics()
        assert "agent_backend_calls_total" in text
        assert "agent_backend_errors_total" in text
        assert "agent_backend_retry_total" in text

    def test_prometheus_format(self):
        """指標應該符合 Prometheus 文本格式。"""
        inc_counter("format_test")
        text = render_prometheus_metrics()
        lines = text.strip().split("\n")
        for line in lines:
            if line.startswith("#"):
                continue
            # 每行應該是 name value 或 name{labels} value
            parts = line.split()
            assert len(parts) >= 2, f"無效格式: {line}"
