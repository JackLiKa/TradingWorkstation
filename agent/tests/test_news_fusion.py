"""news_fusion 單元測試 — RRF 雙路召回融合。"""

import pytest

from app.services.news_fusion import reciprocal_rank_fusion


class TestRRFFusion:
    def test_both_paths_overlap(self):
        """兩路檢索有重疊結果 → 重疊項 RRF 分數最高。"""
        vector_results = [
            {"uri": "a", "title": "央行降準", "summary": "", "similarity": 0.9},
            {"uri": "b", "title": "半導體利好", "summary": "", "similarity": 0.8},
            {"uri": "c", "title": "新能源補貼", "summary": "", "similarity": 0.7},
        ]
        bm25_results = [
            {"uri": "b", "title": "半導體利好", "summary": "", "bm25_score": 5.0},
            {"uri": "a", "title": "央行降準", "summary": "", "bm25_score": 3.0},
            {"uri": "d", "title": "芯片漲價", "summary": "", "bm25_score": 2.0},
        ]
        fused = reciprocal_rank_fusion(vector_results, bm25_results, top_k=10)
        # "a" 和 "b" 兩路都命中，分數應該最高
        assert len(fused) == 4  # a, b, c, d
        uris = [f["uri"] for f in fused]
        assert "a" in uris
        assert "b" in uris
        # 兩路命中的應該排在前面
        top_two = {fused[0]["uri"], fused[1]["uri"]}
        assert top_two == {"a", "b"}

    def test_vector_only(self):
        """只有向量檢索結果。"""
        vector_results = [
            {"uri": "a", "title": "央行降準", "summary": "", "similarity": 0.9},
        ]
        fused = reciprocal_rank_fusion(vector_results, [], top_k=10)
        assert len(fused) == 1
        assert fused[0]["uri"] == "a"
        assert fused[0]["vector_rank"] == 1
        assert fused[0]["bm25_rank"] == 0

    def test_bm25_only(self):
        """只有 BM25 檢索結果。"""
        bm25_results = [
            {"uri": "x", "title": "芯片漲價", "summary": "", "bm25_score": 5.0},
        ]
        fused = reciprocal_rank_fusion([], bm25_results, top_k=10)
        assert len(fused) == 1
        assert fused[0]["uri"] == "x"
        assert fused[0]["vector_rank"] == 0
        assert fused[0]["bm25_rank"] == 1

    def test_both_empty(self):
        """兩路都為空。"""
        fused = reciprocal_rank_fusion([], [], top_k=10)
        assert fused == []

    def test_top_k_limit(self):
        """top_k 限制返回條數。"""
        vector_results = [{"uri": f"v{i}", "title": f"新聞{i}", "summary": ""} for i in range(20)]
        bm25_results = [{"uri": f"b{i}", "title": f"文章{i}", "summary": ""} for i in range(20)]
        fused = reciprocal_rank_fusion(vector_results, bm25_results, top_k=5)
        assert len(fused) == 5

    def test_rrf_score_present(self):
        """融合結果包含 rrf_score 字段。"""
        vector_results = [{"uri": "a", "title": "央行", "summary": "", "similarity": 0.9}]
        bm25_results = [{"uri": "a", "title": "央行", "summary": "", "bm25_score": 3.0}]
        fused = reciprocal_rank_fusion(vector_results, bm25_results, top_k=10)
        assert "rrf_score" in fused[0]
        assert fused[0]["rrf_score"] > 0

    def test_metadata_preserved(self):
        """融合結果保留 title/summary/source 等元數據。"""
        vector_results = [{
            "uri": "a", "title": "央行降準", "summary": "貨幣政策",
            "source": "華爾街見聞", "channel": "a-stock",
            "date": "2026-08-25", "url": "http://example.com/1",
            "similarity": 0.9,
        }]
        fused = reciprocal_rank_fusion(vector_results, [], top_k=10)
        assert fused[0]["title"] == "央行降準"
        assert fused[0]["source"] == "華爾街見聞"
        assert fused[0]["channel"] == "a-stock"
        assert fused[0]["url"] == "http://example.com/1"

    def test_freshness_bonus(self):
        """最近 3 天的新聞有新鮮度加分。"""
        from datetime import datetime, timezone
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        old_date = "2020-01-01"

        vector_results = [
            {"uri": "new", "title": "新聞A", "summary": "", "date": today, "similarity": 0.5},
            {"uri": "old", "title": "新聞B", "summary": "", "date": old_date, "similarity": 0.5},
        ]
        fused = reciprocal_rank_fusion(vector_results, [], top_k=10)
        # 兩條向量排名相同（1 和 2），但新聞 A 有新鮮度加分，應該排第一
        assert fused[0]["uri"] == "new"
