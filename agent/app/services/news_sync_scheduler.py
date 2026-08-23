"""新聞自動同步排程器 — 使用 APScheduler 定期抓取最新新聞 + 啟動時補抓。

功能：
1. 啟動時補抓：系統啟動時追回停機期間漏掉的新聞（默認 7 天）
2. 定時同步：每 6 分鐘自動抓取最新新聞（全頻道），存入向量庫 + MySQL

配置（agent/.env）：
- NEWS_SYNC_ENABLED=true/false（默認 true）
- NEWS_SYNC_INTERVAL=360（秒，默認 6 分鐘）
- NEWS_SYNC_CATCHUP_DAYS=7（啟動時補抓天數）
- NEWS_SYNC_CHANNELS=all/a-stock（同步頻道）
- NEWS_SYNC_CATCHUP_ON_STARTUP=true/false（默認 true）
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings

logger = logging.getLogger("agent.news_sync")


class NewsSyncScheduler:
    """新聞自動同步排程器。"""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._last_sync_result: dict = {}
        self._last_catchup_result: dict = {}
        self._catchup_done = False

    @property
    def last_sync_result(self) -> dict:
        return self._last_sync_result

    @property
    def last_catchup_result(self) -> dict:
        return self._last_catchup_result

    @property
    def catchup_done(self) -> bool:
        return self._catchup_done

    def start(self):
        """啟動新聞同步排程。"""
        if not settings.news_sync_enabled:
            logger.info("新聞自動同步已禁用 (NEWS_SYNC_ENABLED=false)")
            return

        # 1. 啟動時補抓（異步任務，不阻塞啟動）
        if settings.news_sync_catchup_on_startup:
            self._scheduler.add_job(
                self._catchup,
                id="news_catchup_initial",
                replace_existing=True,
            )
            logger.info(
                f"新聞補抓任務已排程: 補抓 {settings.news_sync_catchup_days} 天, "
                f"頻道={settings.news_sync_channels}"
            )

        # 2. 定時同步（每 NEWS_SYNC_INTERVAL 秒）
        self._scheduler.add_job(
            self._sync,
            "interval",
            seconds=settings.news_sync_interval,
            id="news_sync",
            replace_existing=True,
            # 補抓完成後再開始定時同步（避免衝突）
            next_run_time=None,  # 手動啟動
        )
        logger.info(f"新聞定時同步已排程: 間隔 {settings.news_sync_interval}s")

        self._scheduler.start()
        logger.info("新聞同步排程器已啟動")

    async def stop(self):
        """停止排程。"""
        self._scheduler.shutdown(wait=False)
        logger.info("新聞同步排程器已停止")

    async def _catchup(self):
        """啟動時補抓漏掉的新聞。"""
        try:
            from app.services import news_store

            channels = None  # None = 全頻道
            if settings.news_sync_channels and settings.news_sync_channels != "all":
                channels = [settings.news_sync_channels]

            logger.info("開始補抓新聞...")
            result = await news_store.catchup_news(
                channels=channels,
                catchup_days=settings.news_sync_catchup_days,
            )
            self._last_catchup_result = result
            self._catchup_done = True
            logger.info(
                f"補抓完成: {result['fetched']} 條新新聞, "
                f"向量庫 stored={result['stored']}, MySQL stored={result['mysql_stored']}, "
                f"耗時 {result['duration_seconds']}s"
            )

            # 補抓完成後，啟動定時同步
            await self._sync()
        except Exception as e:
            logger.error(f"新聞補抓異常: {e}")
            self._catchup_done = True
            # 即使補抓失敗，也啟動定時同步
            await self._sync()

    async def _sync(self):
        """定時同步最新新聞。"""
        try:
            from app.services import news_store

            channel = settings.news_sync_channels or "all"
            result = await news_store.sync_news_to_vector_store(
                channel=channel,
                limit=50,
            )
            self._last_sync_result = result
            logger.info(
                f"定時同步完成: fetched={result['fetched']}, "
                f"向量庫 stored={result['stored']}, MySQL stored={result['mysql_stored']}"
            )
        except Exception as e:
            logger.error(f"新聞定時同步異常: {e}")


news_sync_scheduler = NewsSyncScheduler()
