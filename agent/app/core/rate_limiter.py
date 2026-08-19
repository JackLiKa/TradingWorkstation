"""速率限制器 — 防止 Agent 高頻迭代壓垮後端 API。

令牌桶算法：
- 桶容量 = max_burst（允許短時間突發）
- 補充速率 = rate_per_second（長期平均速率）
- 每次調用消耗 1 個令牌
- 令牌不足時等待（而非直接拒絕，避免優化循環中斷）

按端點類型分組限制：
- backtest: 重計算，嚴格限制（每 30 秒 1 次）
- screener: 中等計算，中等限制（每 5 秒 1 次）
- 其他讀操作: 輕量，寬鬆限制（每秒 5 次）
"""
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("agent.ratelimit")


class TokenBucket:
    """令牌桶速率限制器。"""

    def __init__(self, rate_per_second: float, max_burst: int):
        """
        Args:
            rate_per_second: 令牌補充速率（每秒）
            max_burst: 桶容量（最大突發數）
        """
        self.rate = rate_per_second
        self.max_burst = max_burst
        self._tokens = float(max_burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, timeout: float = 60.0) -> bool:
        """獲取一個令牌（等待直到有令牌或超時）。

        Args:
            timeout: 最大等待時間（秒）

        Returns:
            bool: 是否成功獲取令牌
        """
        start = time.monotonic()
        while True:
            async with self._lock:
                # 補充令牌
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self.max_burst, self._tokens + elapsed * self.rate)
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True

                # 計算需要等待的時間
                wait_time = (1.0 - self._tokens) / self.rate

            # 檢查是否超時
            if time.monotonic() - start + wait_time > timeout:
                logger.warning(f"速率限制等待超時 ({timeout}s)")
                return False

            await asyncio.sleep(min(wait_time, 1.0))


# 按端點類型的速率限制器
_buckets: dict[str, TokenBucket] = {}

# 速率配置（可通過環境變量調整）
import os
BACKTEST_RATE = float(os.environ.get("RATE_LIMIT_BACKTEST", "0.033"))  # 每 30 秒 1 次
SCREENER_RATE = float(os.environ.get("RATE_LIMIT_SCREENER", "0.2"))    # 每 5 秒 1 次
READ_RATE = float(os.environ.get("RATE_LIMIT_READ", "5.0"))            # 每秒 5 次


def _get_bucket(endpoint: str) -> TokenBucket:
    """根據端點類型獲取對應的速率限制器。"""
    if endpoint not in _buckets:
        if "backtest" in endpoint:
            _buckets[endpoint] = TokenBucket(rate_per_second=BACKTEST_RATE, max_burst=2)
        elif "screener" in endpoint:
            _buckets[endpoint] = TokenBucket(rate_per_second=SCREENER_RATE, max_burst=3)
        else:
            _buckets[endpoint] = TokenBucket(rate_per_second=READ_RATE, max_burst=10)
        logger.info(f"速率限制器創建: {endpoint} (rate={_buckets[endpoint].rate}/s)")
    return _buckets[endpoint]


async def acquire(endpoint: str, timeout: float = 60.0) -> bool:
    """獲取調用許可（等待直到允許或超時）。

    Args:
        endpoint: API 端點路徑（如 "api/backtest/run"）
        timeout: 最大等待時間

    Returns:
        bool: 是否獲得許可
    """
    bucket = _get_bucket(endpoint)
    return await bucket.acquire(timeout=timeout)


def get_status() -> dict:
    """獲取速率限制器狀態。"""
    return {
        endpoint: {
            "rate_per_second": bucket.rate,
            "max_burst": bucket.max_burst,
            "current_tokens": round(bucket._tokens, 2),
        }
        for endpoint, bucket in _buckets.items()
    }
