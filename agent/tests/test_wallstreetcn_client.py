"""測試華爾街見聞新聞抓取客戶端 — wallstreetcn_client.py。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import wallstreetcn_client


class TestCleanHtml:
    """測試 HTML 清洗。"""

    def test_removes_html_tags(self):
        assert wallstreetcn_client._clean_html("<p>hello</p>") == "hello"

    def test_removes_nested_tags(self):
        assert wallstreetcn_client._clean_html("<div><p>text</p></div>") == "text"

    def test_removes_entities(self):
        assert wallstreetcn_client._clean_html("a&nbsp;b&amp;c") == "a b&c"

    def test_empty_input(self):
        assert wallstreetcn_client._clean_html("") == ""
        assert wallstreetcn_client._clean_html(None) == ""

    def test_compresses_whitespace(self):
        assert wallstreetcn_client._clean_html("  hello   world  ") == "hello world"


class TestParseTimestamp:
    """測試時間戳解析。"""

    def test_seconds_timestamp(self):
        # 1787155200 = 2026-08-19 16:00:00 UTC（台灣時間 +8 = 2026-08-20 00:00）
        result = wallstreetcn_client._parse_timestamp(1787155200)
        assert "2026-08-" in result
        assert len(result) == 19  # YYYY-MM-DD HH:MM:SS

    def test_milliseconds_timestamp(self):
        result = wallstreetcn_client._parse_timestamp(1787155200000)
        assert "2026-08-" in result

    def test_empty(self):
        assert wallstreetcn_client._parse_timestamp(0) == ""
        assert wallstreetcn_client._parse_timestamp(None) == ""

    def test_invalid(self):
        assert wallstreetcn_client._parse_timestamp("invalid") == ""


class TestNormalizeArticle:
    """測試文章標準化。"""

    def test_standard_article(self):
        item = {
            "resource": {
                "uri": "abc123",
                "title": "測試標題",
                "content_short": "<p>摘要內容</p>",
                "display_time": 1787155200,
                "author": {"display_name": "作者"},
                "uri_short": "https://wallstreetcn.com/articles/abc123",
            }
        }
        result = wallstreetcn_client._normalize_article(item, "a-stock")
        assert result["uri"] == "abc123"
        assert result["title"] == "測試標題"
        assert result["summary"] == "摘要內容"
        assert result["source"] == "華爾街見聞"
        assert result["author"] == "作者"
        assert result["channel"] == "a-stock"
        assert "2026-08-" in result["date"]

    def test_missing_resource_uses_item(self):
        item = {"uri": "direct", "title": "直接", "display_time": 1787155200}
        result = wallstreetcn_client._normalize_article(item, "global")
        assert result["uri"] == "direct"
        assert result["title"] == "直接"

    def test_empty_item(self):
        result = wallstreetcn_client._normalize_article({}, "global")
        assert result["title"] == ""
        assert result["source"] == "華爾街見聞"


class TestNormalizeLive:
    """測試 7x24 快訊標準化。"""

    def test_standard_live(self):
        item = {
            "id": 12345,
            "title": "快訊標題",
            "content_text": "<p>快訊內容</p>",
            "display_time": 1787155200,
        }
        result = wallstreetcn_client._normalize_live(item, "a-stock")
        assert result["uri"] == "12345"
        assert result["title"] == "快訊標題"
        assert result["summary"] == "快訊內容"
        assert result["channel"] == "a-stock"

    def test_title_fallback_to_content(self):
        item = {"id": 1, "content_text": "內容很長很長很長", "display_time": 1787155200}
        result = wallstreetcn_client._normalize_live(item, "global")
        assert result["title"]  # 應有 fallback


class TestFetchLatestArticles:
    """測試最新文章抓取。"""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "items": [
                    {
                        "resource_type": "article",
                        "resource": {
                            "uri": "test1",
                            "title": "新聞1",
                            "content_short": "摘要",
                            "display_time": 1787155200,
                        }
                    }
                ]
            }
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            articles = await wallstreetcn_client.fetch_latest_articles("a-stock", 10)
            assert len(articles) == 1
            assert articles[0]["title"] == "新聞1"

    @pytest.mark.asyncio
    async def test_failure_returns_empty(self):
        with patch("httpx.AsyncClient", side_effect=Exception("network error")):
            articles = await wallstreetcn_client.fetch_latest_articles("a-stock", 10)
            assert articles == []


class TestSearchArticles:
    """測試關鍵詞搜索。"""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "items": [
                    {
                        "resource_type": "article",
                        "resource": {
                            "uri": "search1",
                            "title": "半導體新聞",
                            "content_short": "摘要",
                            "display_time": 1787155200,
                        }
                    }
                ]
            }
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            articles = await wallstreetcn_client.search_articles("半導體", 5)
            assert len(articles) == 1
            assert articles[0]["title"] == "半導體新聞"

    @pytest.mark.asyncio
    async def test_failure_returns_empty(self):
        with patch("httpx.AsyncClient", side_effect=Exception("error")):
            articles = await wallstreetcn_client.search_articles("test", 5)
            assert articles == []


class TestFetchLiveNews:
    """測試 7x24 快訊抓取。"""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "items": [
                    {"id": 1, "title": "快訊1", "content_text": "內容", "display_time": 1787155200}
                ]
            }
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            lives = await wallstreetcn_client.fetch_live_news("a-stock", 10)
            assert len(lives) == 1
            assert lives[0]["title"] == "快訊1"


class TestChannelMap:
    """測試頻道映射。"""

    def test_all_channels_present(self):
        assert "global" in wallstreetcn_client.CHANNEL_MAP
        assert "a-stock" in wallstreetcn_client.CHANNEL_MAP
        assert "us-stock" in wallstreetcn_client.CHANNEL_MAP
        assert "commodity" in wallstreetcn_client.CHANNEL_MAP

    def test_channel_codes(self):
        assert wallstreetcn_client.CHANNEL_MAP["a-stock"] == "a-stock-channel"
        assert wallstreetcn_client.CHANNEL_MAP["global"] == "global-channel"
