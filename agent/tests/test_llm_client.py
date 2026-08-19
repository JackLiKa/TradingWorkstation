"""測試 LLM 客戶端 — 多模型路由 + 降級邏輯。"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.llm_client import LLMClient, LLMResponse
from app.core.providers import PROVIDERS


class TestLLMClientInit:
    """測試 LLM 客戶端初始化。"""

    def test_has_provider_status(self):
        client = LLMClient()
        assert hasattr(client, "_provider_status")
        assert isinstance(client._provider_status, dict)

    def test_has_fallback_chain(self):
        client = LLMClient()
        assert hasattr(client, "get_fallback_chain")

    def test_model_status_default(self):
        client = LLMClient()
        assert client.model_status.available is False
        assert client.model_status.provider == "unknown"


class TestFallbackChain:
    """測試降級鏈邏輯。"""

    def test_empty_when_nothing_available(self):
        client = LLMClient()
        client._provider_status = {}
        chain = client.get_fallback_chain()
        assert chain == []

    def test_preferred_first(self):
        client = LLMClient()
        client._provider_status = {
            "deepseek-pro": True,
            "glm-flash": True,
            "deepseek-flash": True,
        }
        chain = client.get_fallback_chain("deepseek-pro")
        assert chain[0] == "deepseek-pro"

    def test_fallback_order(self):
        """降級鏈應該按優先級排序。"""
        client = LLMClient()
        client._provider_status = {
            "deepseek-pro": True,
            "glm-flash": True,
            "deepseek-flash": True,
            "devin": True,
        }
        chain = client.get_fallback_chain()
        # glm-flash 應該排第一（免費 + 快）
        assert chain[0] == "glm-flash"
        # devin 應該排最後（延遲高）
        assert chain[-1] == "devin"

    def test_excludes_unavailable(self):
        client = LLMClient()
        client._provider_status = {
            "deepseek-pro": True,
            "glm-flash": False,  # 不可用
        }
        chain = client.get_fallback_chain()
        assert "glm-flash" not in chain
        assert "deepseek-pro" in chain


class TestAnalyzeRouting:
    """測試 analyze() 路由邏輯。"""

    @pytest.fixture
    def client(self):
        c = LLMClient()
        c._provider_status = {"deepseek-flash": True}
        c._model_status.available = True
        return c

    def test_raises_when_no_provider(self):
        client = LLMClient()
        client._provider_status = {}
        client._model_status.available = False
        with patch.object(client, "check_models", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = client._model_status
            with pytest.raises(RuntimeError, match="沒有可用"):
                asyncio.run(client.analyze("test"))

    def test_routes_to_preferred(self, client):
        """應該路由到 preferred_provider。"""
        with patch.object(client, "_call_provider", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "test response"
            result = asyncio.run(client.analyze("test", preferred_provider="deepseek-flash"))
            assert result.text == "test response"
            assert result.provider == "deepseek-flash"
            assert mock_call.call_args[0][0] == "deepseek-flash"

    def test_fallback_on_failure(self, client):
        """主供應商失敗時應該降級。"""
        client._provider_status = {"deepseek-flash": True, "glm-flash": True}

        call_count = 0
        async def mock_call(provider_id, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if provider_id == "deepseek-flash":
                raise RuntimeError("connection error")
            return "fallback response"

        with patch.object(client, "_call_provider", side_effect=mock_call):
            result = asyncio.run(client.analyze("test", preferred_provider="deepseek-flash"))
            assert result.text == "fallback response"
            assert result.fallback_from == "deepseek-flash"
            assert call_count == 2


class TestOpenAICompatibleCall:
    """測試 OpenAI-compatible API 調用。"""

    @pytest.fixture
    def client(self):
        c = LLMClient()
        c._provider_status = {"deepseek-flash": True}
        return c

    def test_call_success(self, client, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "choices": [{"message": {"content": "test output"}}]
        })

        async def mock_post(*args, **kwargs):
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            result = asyncio.run(client._call_provider(
                "deepseek-flash", "test prompt", "system", json_mode=False
            ))
            assert result == "test output"

    def test_call_with_json_mode(self, client, monkeypatch):
        """json_mode=True 應該在請求體中加入 response_format。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        captured_body = {}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "choices": [{"message": {"content": '{"key": "value"}'}}]
        })

        async def mock_post(url, headers=None, json=None):
            captured_body.update(json or {})
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            result = asyncio.run(client._call_provider(
                "deepseek-flash", "test", "system", json_mode=True
            ))
            assert "response_format" in captured_body
            assert captured_body["response_format"]["type"] == "json_object"

    def test_call_no_api_key_raises(self, client, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="API key 未配置"):
            asyncio.run(client._call_provider("deepseek-flash", "test", "system"))
