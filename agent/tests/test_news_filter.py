"""news_filter 單元測試 — 財經關鍵詞過濾器。"""

import pytest

from app.services.news_filter import (
    filter_news_items,
    filter_mixed_news,
    _matches_any,
    _get_keywords,
    _get_blacklist,
)


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    """每個測試前重置過濾器配置。"""
    monkeypatch.setattr("app.services.news_filter.settings.news_filter_enabled", True)
    monkeypatch.setattr("app.services.news_filter.settings.news_filter_keywords", "")
    monkeypatch.setattr("app.services.news_filter.settings.news_filter_blacklist", "")


class TestMatchesAny:
    def test_match_keyword_in_title(self):
        assert _matches_any("央行降準0.5個百分點", {"央行", "降準"})

    def test_no_match(self):
        assert not _matches_any("明星離婚八卦", {"央行", "降準"})

    def test_empty_text(self):
        assert not _matches_any("", {"央行"})

    def test_case_insensitive(self):
        assert _matches_any("Nvidia earnings beat", {"nvidia"})


class TestGetKeywords:
    def test_default_keywords(self):
        kws = _get_keywords()
        assert "央行" in kws
        assert "英偉達" in kws
        assert len(kws) > 50

    def test_env_override(self, monkeypatch):
        monkeypatch.setattr("app.services.news_filter.settings.news_filter_keywords", "央行,降準,CPI")
        kws = _get_keywords()
        # .env 自定義關鍵詞全部按中權重（2 分）處理
        assert kws == {"央行": 2, "降準": 2, "CPI": 2}


class TestGetBlacklist:
    def test_default_blacklist(self):
        bl = _get_blacklist()
        assert "廣告" in bl
        assert "彩票" in bl

    def test_env_append(self, monkeypatch):
        monkeypatch.setattr("app.services.news_filter.settings.news_filter_blacklist", "測試黑名詞")
        bl = _get_blacklist()
        assert "測試黑名詞" in bl
        assert "廣告" in bl  # 默認仍在


class TestFilterNewsItems:
    def test_filter_disabled_returns_all(self, monkeypatch):
        monkeypatch.setattr("app.services.news_filter.settings.news_filter_enabled", False)
        items = [{"title": "明星八卦新聞", "summary": ""}, {"title": "央行降準", "summary": ""}]
        assert filter_news_items(items, source_type="live") == items

    def test_live_filters_no_keyword(self):
        """7x24 快訊無關鍵詞的應被過濾。"""
        items = [
            {"title": "央行宣布降準0.5個百分點", "summary": "", "channel": "live"},
            {"title": "某明星出席活動", "summary": "娛樂圈動態", "channel": "live"},
        ]
        result = filter_news_items(items, source_type="live")
        assert len(result) == 1
        assert "央行" in result[0]["title"]

    def test_article_keeps_with_low_score(self):
        """深度文章閾值低（1 分），命中低權重詞即可保留，無關鍵詞則過濾。"""
        items = [
            {"title": "深度分析：全球經濟走勢與反彈", "summary": "長篇分析文章"},  # "反彈"=1分
            {"title": "某地區天氣預報更新", "summary": "未來一周天氣"},  # 0分，過濾
        ]
        result = filter_news_items(items, source_type="article")
        assert len(result) == 1  # 只保留命中關鍵詞的
        assert "反彈" in result[0]["title"]

    def test_blacklist_filters_all_sources(self):
        """黑名單對所有來源生效。"""
        items = [
            {"title": "央行降準（廣告推廣）", "summary": "", "channel": "live"},
            {"title": "彩票中獎秘訣", "summary": "", "channel": "live"},
        ]
        result = filter_news_items(items, source_type="live")
        assert len(result) == 0

    def test_short_title_filtered(self):
        """過短標題過濾。"""
        items = [
            {"title": "央行", "summary": "降準消息", "channel": "live"},  # 2字符，過短
            {"title": "央行宣布降準0.5個百分點", "summary": "", "channel": "live"},
        ]
        result = filter_news_items(items, source_type="live")
        assert len(result) == 1
        assert "降準0.5" in result[0]["title"]

    def test_empty_items(self):
        assert filter_news_items([], source_type="live") == []

    def test_summary_keyword_match(self):
        """標題無關鍵詞但摘要有也保留（標題需達最小長度）。"""
        items = [
            {"title": "最新市場動態消息", "summary": "美聯儲宣布加息50基點", "channel": "live"},
        ]
        result = filter_news_items(items, source_type="live")
        assert len(result) == 1


class TestFilterMixedNews:
    def test_mixed_separates_live_and_article(self):
        """混合來源：article 寬鬆 + live 嚴格。"""
        items = [
            {"title": "深度分析全球經濟與反彈", "summary": "長文", "channel": "a-stock"},  # "反彈"=1分
            {"title": "某明星出席活動", "summary": "娛樂", "channel": "live"},
            {"title": "央行降準重磅消息", "summary": "", "channel": "live"},
        ]
        result = filter_mixed_news(items)
        # article 保留 1 條（命中"反彈"=1分），live 保留 1 條（命中"央行"=3分+"重磅"=3分）
        assert len(result) == 2

    def test_mixed_disabled(self, monkeypatch):
        monkeypatch.setattr("app.services.news_filter.settings.news_filter_enabled", False)
        items = [{"title": "test", "summary": "", "channel": "live"}]
        assert filter_mixed_news(items) == items

    def test_mixed_empty(self):
        assert filter_mixed_news([]) == []
