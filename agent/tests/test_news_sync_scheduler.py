"""測試新聞自動同步排程器 — 補抓 + 定時同步。

覆蓋：
- NewsSyncScheduler 啟動/停止
- 補抓函數 catchup_news（mock wallstreetcn_client）
- cursor 分頁函數 fetch_articles_catchup
- _fetch_latest_articles_with_cursor 返回 next_cursor
- 配置項讀取
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.news_sync_scheduler import NewsSyncScheduler


@pytest.fixture
def scheduler():
    """創建一個 NewsSyncScheduler 實例。"""
    return NewsSyncScheduler()


class TestNewsSyncScheduler:
    """測試新聞同步排程器。"""

    def test_scheduler_init(self, scheduler):
        """排程器初始化應該有默認狀態。"""
        assert scheduler.catchup_done is False
        assert scheduler.last_sync_result == {}
        assert scheduler.last_catchup_result == {}

    @patch("app.services.news_sync_scheduler.settings")
    def test_start_disabled(self, mock_settings, scheduler):
        """NEWS_SYNC_ENABLED=false 時不應啟動排程。"""
        mock_settings.news_sync_enabled = False
        scheduler.start()
        # 排程器未啟動，不應有活躍的 job
        assert scheduler._scheduler.running is False

    @pytest.mark.asyncio
    @patch("app.services.news_sync_scheduler.settings")
    async def test_start_enabled(self, mock_settings, scheduler):
        """NEWS_SYNC_ENABLED=true 時應排程補抓 + 定時同步。"""
        mock_settings.news_sync_enabled = True
        mock_settings.news_sync_catchup_on_startup = True
        mock_settings.news_sync_interval = 360
        mock_settings.news_sync_catchup_days = 7
        mock_settings.news_sync_channels = "all"

        scheduler.start()
        assert scheduler._scheduler.running is True
        jobs = scheduler._scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        assert "news_catchup_initial" in job_ids
        assert "news_sync" in job_ids
        scheduler._scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    @patch("app.services.news_sync_scheduler.settings")
    async def test_catchup_flow(self, mock_settings, scheduler):
        """補抓流程應該調用 catchup_news 並更新狀態。"""
        mock_settings.news_sync_catchup_days = 7
        mock_settings.news_sync_channels = "all"

        mock_result = {
            "channels": 6,
            "fetched": 100,
            "stored": 80,
            "duplicated": 20,
            "failed": 0,
            "mysql_stored": 80,
            "mysql_duplicated": 20,
            "duration_seconds": 30.5,
        }

        with patch("app.services.news_store.catchup_news", new_callable=AsyncMock) as mock_catchup:
            mock_catchup.return_value = mock_result
            with patch("app.services.news_store.sync_news_to_vector_store", new_callable=AsyncMock) as mock_sync:
                mock_sync.return_value = {"fetched": 50, "stored": 10, "duplicated": 40, "failed": 0, "mysql_stored": 10, "mysql_duplicated": 40}

                scheduler._scheduler.start()
                await scheduler._catchup()

                assert scheduler.catchup_done is True
                assert scheduler.last_catchup_result == mock_result
                assert mock_catchup.called
                scheduler._scheduler.shutdown(wait=False)


class TestFetchArticlesCatchup:
    """測試 cursor 分頁補抓函數。"""

    @pytest.mark.asyncio
    async def test_catchup_stops_on_empty(self):
        """無文章時應立即停止。"""
        from app.services import wallstreetcn_client

        with patch.object(
            wallstreetcn_client, "_fetch_latest_articles_with_cursor",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = ([], "")
            result = await wallstreetcn_client.fetch_articles_catchup(
                channel="a-stock", max_pages=5
            )
            assert result == []
            assert mock_fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_catchup_stops_on_existing_uris(self):
        """遇到已存在的 URI 應停止翻頁。"""
        from app.services import wallstreetcn_client

        page1 = [
            {"uri": "new1", "title": "新聞1", "date": "2026-08-23 10:00:00", "channel": "a-stock"},
            {"uri": "old1", "title": "舊聞1", "date": "2026-08-22 10:00:00", "channel": "a-stock"},
        ]
        page2 = [
            {"uri": "old2", "title": "舊聞2", "date": "2026-08-21 10:00:00", "channel": "a-stock"},
        ]

        with patch.object(
            wallstreetcn_client, "_fetch_latest_articles_with_cursor",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.side_effect = [
                (page1, "cursor2"),
                (page2, ""),
            ]
            with patch.object(wallstreetcn_client, "asyncio", new=MagicMock()) as mock_aio:
                mock_aio.sleep = AsyncMock()

                result = await wallstreetcn_client.fetch_articles_catchup(
                    channel="a-stock",
                    max_pages=5,
                    existing_uris={"old1", "old2"},
                )
                # new1 是新的，old1 已存在 → hit_existing=True, new_count=1
                # 但 new_count != 0 所以繼續翻頁
                # page2 全是 old2 已存在 → new_count=0, hit_existing=True → 停止
                assert len(result) == 1
                assert result[0]["uri"] == "new1"
                assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_catchup_filters_by_cutoff_date(self):
        """早於 cutoff_date 的文章應被過濾。"""
        from app.services import wallstreetcn_client

        articles = [
            {"uri": "new1", "title": "新聞1", "date": "2026-08-23 10:00:00", "channel": "a-stock"},
            {"uri": "old1", "title": "舊聞1", "date": "2026-08-10 10:00:00", "channel": "a-stock"},
        ]

        with patch.object(
            wallstreetcn_client, "_fetch_latest_articles_with_cursor",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = (articles, "")
            result = await wallstreetcn_client.fetch_articles_catchup(
                channel="a-stock",
                max_pages=5,
                cutoff_date="2026-08-15",
            )
            assert len(result) == 1
            assert result[0]["uri"] == "new1"

    @pytest.mark.asyncio
    async def test_catchup_max_pages_limit(self):
        """應遵守 max_pages 限制。"""
        from app.services import wallstreetcn_client

        pages = [
            ([{"uri": f"new{idx}", "title": f"新聞{idx}", "date": "2026-08-23 10:00:00", "channel": "a-stock"}], "next_cursor")
            for idx in range(10)
        ]

        with patch.object(
            wallstreetcn_client, "_fetch_latest_articles_with_cursor",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.side_effect = pages
            with patch.object(wallstreetcn_client, "asyncio", new=MagicMock()) as mock_aio:
                mock_aio.sleep = AsyncMock()

                result = await wallstreetcn_client.fetch_articles_catchup(
                    channel="a-stock",
                    max_pages=3,
                )
                assert mock_fetch.call_count == 3
                assert len(result) == 3  # 每頁 1 條，3 頁 = 3 條


class TestFetchWithCursor:
    """測試 _fetch_latest_articles_with_cursor。"""

    @pytest.mark.asyncio
    async def test_returns_articles_and_cursor(self):
        """應返回 (articles, next_cursor) 元組。"""
        from app.services import wallstreetcn_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "items": [],
                "next_cursor": "abc123",
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            articles, cursor = await wallstreetcn_client._fetch_latest_articles_with_cursor(
                channel="a-stock", limit=20
            )
            assert articles == []
            assert cursor == "abc123"

    @pytest.mark.asyncio
    async def test_backward_compatible_raw_function(self):
        """_fetch_latest_articles_raw 應保持向後兼容（只返回 list）。"""
        from app.services import wallstreetcn_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "items": [],
                "next_cursor": "abc",
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await wallstreetcn_client._fetch_latest_articles_raw(
                channel="a-stock", limit=20
            )
            assert isinstance(result, list)
