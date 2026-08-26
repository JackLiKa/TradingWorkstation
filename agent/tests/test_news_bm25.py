"""news_bm25 單元測試 — BM25 關鍵詞檢索。"""

import pytest

from app.services.news_bm25 import (
    _tokenize,
    _build_index,
    _ensure_index,
    search_bm25,
    is_available,
    get_status,
    rebuild_index,
)


@pytest.fixture(autouse=True)
def _reset_index():
    """每個測試前重置 BM25 索引。"""
    rebuild_index([])


class TestTokenize:
    def test_basic_tokenize(self):
        tokens = _tokenize("央行宣布降準0.5個百分點")
        assert "央行" in tokens
        assert "降準" in tokens

    def test_empty_text(self):
        assert _tokenize("") == []

    def test_filter_short_words(self):
        """單字符詞被過濾。"""
        tokens = _tokenize("A股市場")
        # "A" 和 "市" 等單字符詞被過濾
        for t in tokens:
            assert len(t) >= 2

    def test_filter_digits(self):
        """純數字被過濾。"""
        tokens = _tokenize("2024年央行降準")
        assert "2024" not in tokens
        assert "央行" in tokens


class TestBuildIndex:
    def test_build_with_documents(self):
        docs = [
            {"title": "央行降準0.5個百分點", "summary": "貨幣政策寬鬆"},
            {"title": "半導體行業利好", "summary": "芯片漲價"},
            {"title": "某明星出席活動", "summary": "娛樂圈動態"},
        ]
        assert _build_index(docs) is True

    def test_build_empty(self):
        assert _build_index([]) is False

    def test_ensure_index_with_documents(self):
        docs = [{"title": "央行降準", "summary": ""}]
        assert _ensure_index(docs) is True


class TestSearchBM25:
    def test_search_finds_relevant(self):
        docs = [
            {"title": "央行宣布降準0.5個百分點", "summary": "貨幣政策寬鬆", "uri": "1"},
            {"title": "半導體行業利好消息", "summary": "芯片漲價", "uri": "2"},
            {"title": "某明星出席活動", "summary": "娛樂圈動態", "uri": "3"},
        ]
        results = search_bm25("央行降準", top_k=3, documents=docs)
        assert len(results) > 0
        assert "央行" in results[0]["title"]
        assert results[0]["bm25_score"] > 0

    def test_search_no_match(self):
        docs = [
            {"title": "某明星出席活動", "summary": "娛樂圈動態", "uri": "1"},
        ]
        results = search_bm25("央行降準", top_k=3, documents=docs)
        assert len(results) == 0

    def test_search_empty_query(self):
        docs = [{"title": "央行降準", "summary": "", "uri": "1"}]
        results = search_bm25("", top_k=3, documents=docs)
        assert len(results) == 0

    def test_search_returns_uri_and_metadata(self):
        docs = [
            {"title": "央行降準", "summary": "貨幣政策", "uri": "test-1",
             "source": "華爾街見聞", "channel": "a-stock", "date": "2026-08-25", "url": "http://example.com/1"},
        ]
        results = search_bm25("央行降準", top_k=1, documents=docs)
        assert len(results) == 1
        assert results[0]["uri"] == "test-1"
        assert results[0]["source"] == "華爾街見聞"
        assert results[0]["channel"] == "a-stock"


class TestStatus:
    def test_get_status(self):
        status = get_status()
        assert "available" in status
        assert "index_size" in status
        assert "init_error" in status
