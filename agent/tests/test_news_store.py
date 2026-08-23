"""測試新聞存儲/檢索服務 — news_store.py。

只測試不需要 Milvus/embedding 的純函數邏輯。
向量庫相關功能（store_news, search_relevant_news）需要 Milvus 環境，標記為 skip。
"""

from app.services import news_store


class TestFormatNewsForPrompt:
    """測試新聞格式化為 prompt 文本。"""

    def test_empty_list(self):
        assert news_store.format_news_for_prompt([]) == ""

    def test_single_news(self):
        news = [
            {
                "title": "半導體行業利好",
                "summary": "台積電宣布擴產",
                "source": "華爾街見聞",
                "date": "2026-08-23 10:00:00",
                "url": "https://wallstreetcn.com/articles/123",
                "similarity": 0.85,
            }
        ]
        result = news_store.format_news_for_prompt(news)
        assert "華爾街見聞相關新聞" in result
        assert "半導體行業利好" in result
        assert "台積電宣布擴產" in result
        assert "0.85" in result
        assert "引用格式" in result

    def test_max_items_limit(self):
        news = [
            {"title": f"新聞{i}", "summary": "摘要", "source": "華爾街見聞", "date": "2026-08-23", "url": ""}
            for i in range(20)
        ]
        result = news_store.format_news_for_prompt(news, max_items=5)
        # 只顯示 5 條標題（新聞0~新聞4）
        for i in range(5):
            assert f"新聞{i}" in result
        # 第 6 條不應出現
        assert "新聞5" not in result

    def test_missing_fields_safe(self):
        news = [{"title": "只有標題"}]
        result = news_store.format_news_for_prompt(news)
        assert "只有標題" in result


class TestGetStatus:
    """測試狀態查詢。"""

    def test_status_structure(self):
        status = news_store.get_status()
        assert "available" in status
        assert "collection" in status
        assert "ttl_days" in status
        assert "max_vectors" in status
        assert status["collection"] == "financial_news_vectors"


class TestConfigConstants:
    """測試配置常量。"""

    def test_collection_name(self):
        assert news_store.COLLECTION_NAME == "financial_news_vectors"

    def test_embedding_dim(self):
        assert news_store.EMBEDDING_DIM == 512

    def test_ttl_default(self):
        assert news_store._NEWS_TTL_DAYS >= 1
