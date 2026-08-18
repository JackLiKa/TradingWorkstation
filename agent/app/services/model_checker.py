"""模型可用性定時檢查 — 使用 APScheduler 定期檢查 LLM 提供者可用性。"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.core.llm_client import llm_client

logger = logging.getLogger("agent.model_checker")


class ModelChecker:
    """定時檢查 LLM 模型可用性，動態調整使用的模型。"""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()

    def start(self):
        """啟動定時檢查任務（同步方法，scheduler 內部異步）。"""
        self._scheduler.add_job(
            self._check,
            "interval",
            seconds=settings.model_check_interval,
            id="model_check",
            replace_existing=True,
        )
        # 啟動時立即檢查一次
        self._scheduler.add_job(
            self._check,
            id="model_check_initial",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(f"模型檢查定時任務已啟動，間隔 {settings.model_check_interval}s")

    async def stop(self):
        """停止定時檢查。"""
        self._scheduler.shutdown(wait=False)
        logger.info("模型檢查定時任務已停止")

    async def _check(self):
        """執行模型可用性檢查。"""
        try:
            status = await llm_client.check_models()
            logger.info(
                f"模型狀態: provider={status.provider}, model={status.model_name}, "
                f"available={status.available}"
            )
        except Exception as e:
            logger.error(f"模型檢查異常: {e}")


model_checker = ModelChecker()
