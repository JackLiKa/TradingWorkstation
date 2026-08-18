"""日誌配置。"""
import logging
import sys

def setup_logging():
    """配置全局日誌，輸出到 stdout，格式含時間+級別+模塊。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # 降低第三方庫日誌級別
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger("agent")
