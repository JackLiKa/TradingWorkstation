"""測試 backend_client — 重試邏輯和連接池。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.backend_client import MAX_RETRIES, BackendClient


class TestBackendClientInit:
    """測試初始化。"""

    def test_has_shared_client(self):
        """應該有共享 httpx 客戶端（連接池）。"""
        client = BackendClient()
        assert hasattr(client, "_client")
        assert isinstance(client._client, httpx.AsyncClient)

    def test_has_retry_method(self):
        """應該有 _request_with_retry 方法。"""
        client = BackendClient()
        assert hasattr(client, "_request_with_retry")

    def test_has_aclose(self):
        """應該有 aclose 方法用於關閉連接池。"""
        client = BackendClient()
        assert hasattr(client, "aclose")


class TestRetryLogic:
    """測試重試邏輯。"""

    @pytest.fixture
    def client(self):
        return BackendClient()

    def test_5xx_triggers_retry(self, client):
        """5xx 錯誤應該觸發重試。"""
        call_count = 0

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.request = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("503", request=mock_response.request, response=mock_response)
        )

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response

        client._client.get = mock_get

        with patch("app.services.backend_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(client._request_with_retry("GET", "http://test", timeout=5))

        assert call_count == MAX_RETRIES, f"應該重試 {MAX_RETRIES} 次，實際 {call_count}"

    def test_4xx_no_retry(self, client):
        """4xx 錯誤不應該重試。"""
        call_count = 0

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.request = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("404", request=mock_response.request, response=mock_response)
        )

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response

        client._client.get = mock_get

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(client._request_with_retry("GET", "http://test", timeout=5))

        assert call_count == 1, "4xx 不應重試"

    def test_success_no_retry(self, client):
        """成功響應不應該重試。"""
        call_count = 0

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"success": True, "data": {}})

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response

        client._client.get = mock_get

        result = asyncio.run(client._request_with_retry("GET", "http://test", timeout=5))
        assert result["success"] is True
        assert call_count == 1

    def test_connect_error_triggers_retry(self, client):
        """連接錯誤應該觸發重試。"""
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("connection refused")

        client._client.get = mock_get

        with patch("app.services.backend_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError):
                asyncio.run(client._request_with_retry("GET", "http://test", timeout=5))

        assert call_count == MAX_RETRIES


class TestBackendClientHealth:
    """測試健康檢查。"""

    def test_health_returns_bool(self):
        """health() 應該返回布爾值。"""
        client = BackendClient()

        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_get(*args, **kwargs):
            return mock_response

        client._client.get = mock_get
        result = asyncio.run(client.health())
        assert result is True

    def test_health_failure_returns_false(self):
        """健康檢查失敗應該返回 False，不拋異常。"""
        client = BackendClient()

        async def mock_get(*args, **kwargs):
            raise httpx.ConnectError("refused")

        client._client.get = mock_get
        result = asyncio.run(client.health())
        assert result is False


class TestDataRange:
    """測試 get_data_range 和 get_latest_trade_date。"""

    def test_get_data_range_success(self):
        """get_data_range 應該返回 (earliest, latest) 元組。"""
        client = BackendClient()

        mock_data = {
            "success": True,
            "data": {
                "earliestTradeDate": "2021-01-04",
                "latestTradeDate": "2026-08-20",
            },
        }

        async def mock_request(*args, **kwargs):
            return mock_data

        client._request_with_retry = mock_request
        earliest, latest = asyncio.run(client.get_data_range())
        assert earliest == "2021-01-04"
        assert latest == "2026-08-20"

    def test_get_data_range_failure_returns_none(self):
        """get_data_range 後端不可用時應返回 (None, None)。"""
        client = BackendClient()

        async def mock_request(*args, **kwargs):
            raise httpx.ConnectError("refused")

        client._request_with_retry = mock_request
        earliest, latest = asyncio.run(client.get_data_range())
        assert earliest is None
        assert latest is None

    def test_get_data_range_missing_fields(self):
        """get_data_range 缺少字段時應返回 (None, None)。"""
        client = BackendClient()

        mock_data = {"success": True, "data": {}}

        async def mock_request(*args, **kwargs):
            return mock_data

        client._request_with_retry = mock_request
        earliest, latest = asyncio.run(client.get_data_range())
        assert earliest is None
        assert latest is None
