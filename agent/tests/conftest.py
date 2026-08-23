"""pytest 配置 — 設置測試環境。"""

import os
import sys
from pathlib import Path

import pytest

# 將 agent 目錄加入 sys.path（讓 tests 能 import app.*）
agent_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(agent_root))

# 測試環境變量（避免載入真實 .env）
os.environ.setdefault("DEVIN_API_KEY", "test-key")
os.environ.setdefault("QODER_PERSONAL_ACCESS_TOKEN", "test-token")
os.environ.setdefault("BACKEND_API_URL", "http://localhost:8090/TradingWorkstation")
os.environ.setdefault("AGENT_PORT", "8100")
os.environ.setdefault("LOG_LEVEL", "WARNING")

# 啟用 wallstreetcn_client 節流器測試模式（禁用 5 分鐘等待）
from app.services.wallstreetcn_client import _throttle

_throttle.enable_test_mode()


@pytest.fixture(autouse=True)
def _reset_throttle_cache():
    """每個測試前清理全局節流器緩存，避免測試間污染。"""
    _throttle._cache.clear()
    _throttle._last_request_time = 0.0
    yield
    _throttle._cache.clear()
