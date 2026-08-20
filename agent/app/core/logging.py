"""日誌配置 — 控制台 + 文件雙輸出 + 輪轉 + 可配置級別。

工程化改進：
- 控制台輸出（UTF-8）+ 文件輸出（自動輪轉 10MB × 5 份）
- 日誌級別可通過環境變量 LOG_LEVEL 配置（DEBUG/INFO/WARNING/ERROR）
- 第三方庫日誌降級（httpx/uvicorn 等）
- 敏感信息過濾（API Key 等）
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 日誌級別可通過環境變量配置
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# 日誌文件路徑
_log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
_log_file = _log_dir / "agent.log"


class SensitiveDataFilter(logging.Filter):
    """過濾日誌中的敏感信息（API Key、Token 等）。"""

    SENSITIVE_PATTERNS = [
        ("Bearer ", "Bearer ***"),
        ("api_key=", "api_key=***"),
        ("API_KEY=", "API_KEY=***"),
        ("access_token=", "access_token=***"),
        ("DEVIN_API_KEY", "DEVIN_API_KEY=***"),
        ("QODER_PERSONAL_ACCESS_TOKEN", "QODER_PERSONAL_ACCESS_TOKEN=***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            if pattern in msg:
                record.msg = msg.replace(pattern, replacement)
                record.args = ()
        return True


def setup_logging():
    """配置全局日誌：控制台 + 文件雙輸出 + 輪轉 + 敏感信息過濾。"""
    # 創建日誌目錄
    _log_dir.mkdir(exist_ok=True)

    # 根 logger 配置
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # 清除現有 handler（避免重複）
    root_logger.handlers.clear()

    # 日誌格式
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # === 控制台 handler ===
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(fmt)
    console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)

    # === 文件 handler（輪轉：10MB × 5 份）===
    file_handler = RotatingFileHandler(
        _log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(fmt)
    file_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(file_handler)

    # 降低第三方庫日誌級別
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("pymilvus").setLevel(logging.WARNING)

    logging.info(f"日誌系統初始化: level={LOG_LEVEL}, file={_log_file}")


logger = logging.getLogger("agent")
