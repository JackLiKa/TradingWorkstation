"""測試新聞 LLM 雙維度重排序服務 — news_reranker.py。

覆蓋：
- 分類函數 _classify_news
- 綜合分數 _composite_score
- prompt 構建
- LLM 響應解析（正常/異常/降級）
- rerank_news 降級路徑
- search_with_rerank 降級路徑
- format_reranked_news_for_prompt 格式化
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import news_reranker


class TestClassifyNews:
    """測試新聞分類函數。"""

    def test_sustained_bullish(self):
        assert news_reranker._classify_news(8, 9) == "持續性利好"
        assert news_reranker._classify_news(5, 6) == "持續性利好"

    def test_one_day_bullish(self):
        assert news_reranker._classify_news(8, 2) == "一日遊利好"
        assert news_reranker._classify_news(5, 3) == "一日遊利好"

    def test_weak_bullish(self):
        assert news_reranker._classify_news(4, 8) == "弱利好"
        assert news_reranker._classify_news(3.5, 5) == "弱利好"

    def test_sustained_bearish(self):
        assert news_reranker._classify_news(-8, 9) == "持續性利空"
        assert news_reranker._classify_news(-5, 6) == "持續性利空"

    def test_one_day_bearish(self):
        assert news_reranker._classify_news(-8, 2) == "一日遊利空"
        assert news_reranker._classify_news(-5, 3) == "一日遊利空"

    def test_weak_bearish(self):
        assert news_reranker._classify_news(-4, 8) == "弱利空"

    def test_neutral(self):
        assert news_reranker._classify_news(0, 5) == "中性"
        assert news_reranker._classify_news(2, 3) == "中性"
        assert news_reranker._classify_news(-2, 7) == "中性"


class TestCompositeScore:
    """測試綜合分數計算。"""

    def test_sustained_bullish_high_score(self):
        score = news_reranker._composite_score(8, 9)
        assert score == 7.2  # 8*9/10

    def test_one_day_bullish_low_score(self):
        score = news_reranker._composite_score(8, 2)
        assert score == 1.6  # 8*2/10，被持續性壓低

    def test_sustained_bearish_negative(self):
        score = news_reranker._composite_score(-8, 9)
        assert score == -7.2

    def test_one_day_bearish_less_negative(self):
        score = news_reranker._composite_score(-8, 2)
        assert score == -1.6  # 負分但被持續性壓低（影響小）

    def test_neutral_zero(self):
        assert news_reranker._composite_score(0, 10) == 0


class TestBuildRerankPrompt:
    """測試 prompt 構建。"""

    def test_basic_prompt(self):
        candidates = [
            {"title": "半導體擴產利好", "summary": "台積電宣布擴產", "date": "2026-08-23", "channel": "a-stock"},
            {"title": "新能源車銷量下滑", "summary": "比亞迪銷量下滑10%", "date": "2026-08-22", "channel": "a-stock"},
        ]
        prompt = news_reranker._build_rerank_prompt("半導體利好", candidates)
        assert "半導體利好" in prompt
        assert "半導體擴產利好" in prompt
        assert "新能源車銷量下滑" in prompt
        assert "direction" in prompt
        assert "sustainability" in prompt
        assert "JSON" in prompt

    def test_empty_summary(self):
        candidates = [{"title": "標題", "summary": "", "date": "2026-08-23", "channel": ""}]
        prompt = news_reranker._build_rerank_prompt("查詢", candidates)
        assert "標題" in prompt


class TestParseRerankResponse:
    """測試 LLM 響應解析（雙維度版本）。"""

    def test_valid_json(self):
        text = json.dumps([
            {"id": 0, "direction": 8, "sustainability": 9, "label": "持續性利好", "reason": "政策落地"},
            {"id": 1, "direction": -5, "sustainability": 2, "label": "一日遊利空", "reason": "概念炒作"},
        ])
        parsed = news_reranker._parse_rerank_response(text, 2)
        assert parsed is not None
        assert len(parsed) == 2
        assert parsed[0]["direction"] == 8
        assert parsed[0]["sustainability"] == 9
        assert parsed[0]["label"] == "持續性利好"
        assert parsed[1]["direction"] == -5

    def test_markdown_fenced_json(self):
        text = '```json\n[{"id": 0, "direction": 7, "sustainability": 8}]\n```'
        parsed = news_reranker._parse_rerank_response(text, 1)
        assert parsed is not None
        assert parsed[0]["direction"] == 7
        # label 應自動推導
        assert parsed[0]["label"] == "持續性利好"

    def test_json_embedded_in_text(self):
        text = '評分結果：\n[{"id": 0, "direction": 6, "sustainability": 5}]\n以上。'
        parsed = news_reranker._parse_rerank_response(text, 1)
        assert parsed is not None
        assert parsed[0]["direction"] == 6

    def test_empty_response(self):
        assert news_reranker._parse_rerank_response("", 5) is None

    def test_invalid_json(self):
        assert news_reranker._parse_rerank_response("not json at all", 5) is None

    def test_out_of_range_id(self):
        text = json.dumps([{"id": 99, "direction": 10, "sustainability": 10}])
        parsed = news_reranker._parse_rerank_response(text, 3)
        # id 越界被過濾，無有效條目 → None
        assert parsed is None

    def test_missing_fields(self):
        text = json.dumps([{"id": 0}, {"direction": 5}])
        parsed = news_reranker._parse_rerank_response(text, 3)
        assert parsed is None

    def test_direction_range_clamped(self):
        text = json.dumps([{"id": 0, "direction": 15, "sustainability": 20}])
        parsed = news_reranker._parse_rerank_response(text, 1)
        assert parsed is not None
        assert parsed[0]["direction"] == 10  # 被限制到 +10
        assert parsed[0]["sustainability"] == 10  # 被限制到 10

    def test_non_list_json(self):
        text = json.dumps({"id": 0, "direction": 9, "sustainability": 8})
        assert news_reranker._parse_rerank_response(text, 1) is None


class TestRerankNews:
    """測試 rerank_news 主流程。"""

    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        result = await news_reranker.rerank_news("查詢", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_candidates_less_than_topk(self):
        """候選少於等於 top_k 時直接返回，不調用 LLM。"""
        candidates = [{"title": "新聞1", "similarity": 0.5}]
        result = await news_reranker.rerank_news("查詢", candidates, top_k=5)
        assert result == candidates

    @pytest.mark.asyncio
    async def test_llm_unavailable_fallback(self):
        """LLM 調用失敗時降級為向量搜索原序。"""
        candidates = [
            {"title": f"新聞{i}", "similarity": 0.5 - i * 0.01}
            for i in range(15)
        ]
        with patch("app.core.llm_client.llm_client") as mock_llm:
            mock_llm.analyze = AsyncMock(side_effect=RuntimeError("無可用供應商"))
            result = await news_reranker.rerank_news("利好", candidates, top_k=5)
        assert len(result) == 5
        assert result[0]["title"] == "新聞0"

    @pytest.mark.asyncio
    async def test_successful_rerank_with_sustainability(self):
        """LLM 成功雙維度重排序 — 持續性利好應排在一日遊利好前面。"""
        candidates = [
            {"title": f"新聞{i}", "summary": f"摘要{i}", "similarity": 0.5}
            for i in range(15)
        ]
        # 新聞5=持續性利好(dir=8,sus=9)，新聞3=一日遊利好(dir=8,sus=2)
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"id": 5, "direction": 8, "sustainability": 9, "label": "持續性利好", "reason": "政策落地"},
            {"id": 3, "direction": 8, "sustainability": 2, "label": "一日遊利好", "reason": "概念炒作"},
            {"id": 0, "direction": 5, "sustainability": 6, "label": "持續性利好", "reason": "業績拐點"},
            {"id": 1, "direction": -5, "sustainability": 2, "label": "一日遊利空", "reason": "傳聞"},
            {"id": 2, "direction": -8, "sustainability": 8, "label": "持續性利空", "reason": "業績暴雷"},
        ])
        mock_response.provider = "glm-flash"
        mock_response.duration_ms = 200

        with patch("app.core.llm_client.llm_client") as mock_llm:
            mock_llm.analyze = AsyncMock(return_value=mock_response)
            result = await news_reranker.rerank_news("半導體利好", candidates, top_k=5)

        assert len(result) == 5
        # 持續性利好(7.2) > 持續性利好(3.0) > 一日遊利好(1.6) > 一日遊利空(-1.0) > 持續性利空(-6.4)
        assert result[0]["title"] == "新聞5"  # 8*9/10=7.2 最高
        assert result[0]["news_label"] == "持續性利好"
        assert result[0]["rerank_score"] == 7.2
        assert result[0]["direction"] == 8
        assert result[0]["sustainability"] == 9
        assert result[1]["title"] == "新聞0"  # 5*6/10=3.0
        assert result[2]["title"] == "新聞3"  # 8*2/10=1.6 一日遊
        assert result[2]["news_label"] == "一日遊利好"
        # 一日遊利空(-5*2/10=-1.0) 排在持續性利空(-8*8/10=-6.4) 前面（負分越小越後）
        assert result[3]["title"] == "新聞1"  # -1.0
        assert result[4]["title"] == "新聞2"  # -6.4

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json_fallback(self):
        """LLM 返回無效 JSON 時降級。"""
        candidates = [
            {"title": f"新聞{i}", "similarity": 0.5}
            for i in range(15)
        ]
        mock_response = MagicMock()
        mock_response.text = "我無法評分"
        mock_response.provider = "glm-flash"
        mock_response.duration_ms = 100

        with patch("app.core.llm_client.llm_client") as mock_llm:
            mock_llm.analyze = AsyncMock(return_value=mock_response)
            result = await news_reranker.rerank_news("查詢", candidates, top_k=5)

        assert len(result) == 5
        assert result[0]["title"] == "新聞0"


class TestSearchWithRerank:
    """測試 search_with_rerank 完整流程。"""

    @pytest.mark.asyncio
    async def test_news_store_unavailable(self):
        """向量庫不可用時返回空列表。"""
        with patch("app.services.news_store.search_relevant_news", return_value=[]):
            result = await news_reranker.search_with_rerank("查詢", top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_few_candidates_no_rerank(self):
        """向量搜索結果少於 top_k 時不調用 LLM。"""
        candidates = [{"title": "新聞1", "similarity": 0.6}]
        with patch("app.services.news_store.search_relevant_news", return_value=candidates):
            with patch("app.core.llm_client.llm_client") as mock_llm:
                result = await news_reranker.search_with_rerank("查詢", top_k=10)
        assert result == candidates
        mock_llm.analyze.assert_not_called()


class TestFormatRerankedNewsForPrompt:
    """測試重排序新聞格式化。"""

    def test_empty_list(self):
        assert news_reranker.format_reranked_news_for_prompt([]) == ""

    def test_grouped_by_label(self):
        news = [
            {
                "title": "政策落地利好",
                "summary": "財政部發文",
                "date": "2026-08-23",
                "url": "https://wallstreetcn.com/articles/1",
                "direction": 8,
                "sustainability": 9,
                "news_label": "持續性利好",
                "rerank_reason": "政策落地+資金配套",
            },
            {
                "title": "概念炒作",
                "summary": "AI概念股拉升",
                "date": "2026-08-23",
                "url": "https://wallstreetcn.com/articles/2",
                "direction": 7,
                "sustainability": 2,
                "news_label": "一日遊利好",
                "rerank_reason": "無業績支撐",
            },
        ]
        result = news_reranker.format_reranked_news_for_prompt(news)
        assert "持續性利好" in result
        assert "一日遊利好" in result
        assert "政策落地利好" in result
        assert "概念炒作" in result
        assert "方向: +8" in result
        assert "持續性: 9/10" in result
        assert "警惕" in result  # 結尾提示

    def test_only_sustained_bullish(self):
        news = [
            {
                "title": "業績超預期",
                "summary": "Q2淨利潤+50%",
                "date": "2026-08-23",
                "url": "https://wallstreetcn.com/articles/3",
                "direction": 9,
                "sustainability": 8,
                "news_label": "持續性利好",
                "rerank_reason": "業績拐點",
            }
        ]
        result = news_reranker.format_reranked_news_for_prompt(news)
        assert "持續性利好" in result
        assert "業績超預期" in result
        # 不應出現其他標籤的分組標題（### 一日遊利好）
        assert "### 一日遊利好" not in result
