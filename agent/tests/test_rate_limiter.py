"""測試速率限制器。"""
import asyncio
import time

import pytest

from app.core.rate_limiter import TokenBucket, acquire, get_status


class TestTokenBucket:
    """測試令牌桶。"""

    def test_initial_burst(self):
        """初始應該允許突發。"""
        bucket = TokenBucket(rate_per_second=1.0, max_burst=5)
        # 初始有 5 個令牌，應該能連續獲取 5 次
        for _ in range(5):
            result = asyncio.run(bucket.acquire(timeout=0.1))
            assert result is True

    def test_rate_limiting(self):
        """超過突發後應該等待。"""
        bucket = TokenBucket(rate_per_second=10.0, max_burst=2)
        # 消耗初始令牌
        asyncio.run(bucket.acquire(timeout=0.1))
        asyncio.run(bucket.acquire(timeout=0.1))
        # 第三次應該需要等待
        start = time.monotonic()
        result = asyncio.run(bucket.acquire(timeout=1.0))
        elapsed = time.monotonic() - start
        assert result is True
        assert elapsed > 0.05  # 應該有等待

    def test_timeout(self):
        """超時應該返回 False。"""
        bucket = TokenBucket(rate_per_second=0.1, max_burst=1)
        asyncio.run(bucket.acquire(timeout=0.1))  # 消耗唯一令牌
        # 第二次應該超時
        result = asyncio.run(bucket.acquire(timeout=0.05))
        assert result is False


class TestRateLimiterAPI:
    """測試速率限制 API。"""

    def test_acquire_returns_bool(self):
        result = asyncio.run(acquire("test_endpoint", timeout=1.0))
        assert isinstance(result, bool)

    def test_get_status_structure(self):
        status = get_status()
        assert isinstance(status, dict)

    def test_different_endpoints_different_buckets(self):
        """不同端點應該用不同的桶。"""
        asyncio.run(acquire("api/backtest/run", timeout=0.1))
        asyncio.run(acquire("api/screener/run", timeout=0.1))
        asyncio.run(acquire("api/dashboard/summary", timeout=0.1))
        status = get_status()
        # 應該有三個不同的端點
        assert len(status) >= 3
