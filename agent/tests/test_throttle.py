"""測試華爾街見聞 API 請求節流器 — _RequestThrottle。

覆蓋：
- 緩存命中（5 分鐘內相同請求返回緩存）
- 節流等待（間隔不足時等待）
- 測試模式（禁用等待）
- 狀態查詢
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.services.wallstreetcn_client import _RequestThrottle, _throttle


class TestRequestThrottleCache:
    """測試緩存機制。"""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """相同請求第二次返回緩存。"""
        throttle = _RequestThrottle()
        throttle.enable_test_mode()

        call_count = 0

        async def fetch():
            nonlocal call_count
            call_count += 1
            return [f"result_{call_count}"]

        # 第一次請求
        r1 = await throttle.throttled_request("test", fetch, a=1)
        assert r1 == ["result_1"]
        assert call_count == 1

        # 第二次相同請求 → 緩存命中
        r2 = await throttle.throttled_request("test", fetch, a=1)
        assert r2 == ["result_1"]  # 返回緩存，不是 result_2
        assert call_count == 1  # fetch 未被調用

    @pytest.mark.asyncio
    async def test_different_params_no_cache(self):
        """不同參數的請求不命中緩存。"""
        throttle = _RequestThrottle()
        throttle.enable_test_mode()

        call_count = 0

        async def fetch():
            nonlocal call_count
            call_count += 1
            return [f"result_{call_count}"]

        r1 = await throttle.throttled_request("test", fetch, a=1)
        r2 = await throttle.throttled_request("test", fetch, a=2)
        assert r1 == ["result_1"]
        assert r2 == ["result_2"]
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_different_endpoint_no_cache(self):
        """不同端點的請求不命中緩存。"""
        throttle = _RequestThrottle()
        throttle.enable_test_mode()

        call_count = 0

        async def fetch():
            nonlocal call_count
            call_count += 1
            return [f"result_{call_count}"]

        r1 = await throttle.throttled_request("endpoint_a", fetch, a=1)
        r2 = await throttle.throttled_request("endpoint_b", fetch, a=1)
        assert call_count == 2


class TestRequestThrottleThrottling:
    """測試節流等待。"""

    @pytest.mark.asyncio
    async def test_test_mode_no_wait(self):
        """測試模式下不等待。"""
        throttle = _RequestThrottle()
        throttle.enable_test_mode()

        async def fetch():
            return ["result"]

        # 連續兩次不同請求，測試模式下不應等待
        start = time.time()
        await throttle.throttled_request("test1", fetch, a=1)
        await throttle.throttled_request("test2", fetch, a=2)
        elapsed = time.time() - start
        assert elapsed < 1.0  # 不應有顯著等待

    @pytest.mark.asyncio
    async def test_throttle_waits(self):
        """非測試模式下，間隔不足時應等待。"""
        throttle = _RequestThrottle()
        # 不啟用測試模式（使用獨立實例，不受 conftest 全局節流器影響）

        # 模擬上次請求剛發生
        throttle._last_request_time = time.time()

        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        async def fetch():
            return ["result"]

        with patch("asyncio.sleep", mock_sleep):
            await throttle.throttled_request("test", fetch, a=1)

        # 應該有等待
        assert len(sleep_calls) > 0
        assert sleep_calls[0] > 100  # 應等待至少 100 秒（5 分鐘 - elapsed）


class TestRequestThrottleStatus:
    """測試狀態查詢。"""

    def test_initial_status(self):
        throttle = _RequestThrottle()
        status = throttle.get_status()
        assert status["last_request_ago_seconds"] == 0
        assert status["min_interval_seconds"] == 300
        assert status["cache_entries"] == 0
        assert status["next_request_in_seconds"] == 0

    def test_status_after_request(self):
        throttle = _RequestThrottle()
        throttle.enable_test_mode()
        throttle._last_request_time = time.time() - 60  # 60 秒前

        status = throttle.get_status()
        assert status["last_request_ago_seconds"] > 50
        assert status["next_request_in_seconds"] > 200  # 300 - 60 ≈ 240


class TestThrottleIntegration:
    """測試節流器與 fetch 函數的整合。"""

    @pytest.mark.asyncio
    async def test_fetch_latest_articles_uses_throttle(self):
        """fetch_latest_articles 應通過節流器，緩存命中時不重複請求。"""
        # 全局節流器已在 conftest 中啟用測試模式
        _throttle.enable_test_mode()

        from unittest.mock import MagicMock
        from app.services import wallstreetcn_client

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"items": []}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # 第一次請求
            await wallstreetcn_client.fetch_latest_articles("a-stock", 10)
            assert mock_client.get.call_count == 1

            # 第二次相同請求 → 緩存命中，不應再次調用 HTTP
            await wallstreetcn_client.fetch_latest_articles("a-stock", 10)
            assert mock_client.get.call_count == 1  # 仍然是 1
