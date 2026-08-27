"""測試語義檢索查詢擴展方向敏感性 — _enrich_query_directional。

覆蓋：
- 利好查詢擴展為利好特徵詞
- 利空查詢擴展為利空特徵詞
- 中性查詢用通用擴展
- 長查詢不擴展
- 利好利空同時存在時不注入方向
"""

import pytest

from app.services.news_store import _enrich_query_directional


class TestEnrichQueryDirectional:
    """測試方向敏感的查詢擴展。"""

    def test_bullish_query_gets_bullish_context(self):
        """利好查詢應注入利好特徵詞。"""
        result = _enrich_query_directional("利好")
        assert "利好" in result
        assert "政策落地" in result or "業績超預期" in result
        assert "資金" in result and "流入" in result
        # 不應包含利空特徵詞
        assert "虧損" not in result
        assert "風險事件" not in result

    def test_bearish_query_gets_bearish_context(self):
        """利空查詢應注入利空特徵詞。"""
        result = _enrich_query_directional("利空")
        assert "利空" in result
        assert "業績下滑" in result or "虧損" in result
        assert "資金流出" in result
        # 不應包含利好特徵詞
        assert "政策落地" not in result
        assert "業績超預期" not in result

    def test_bullish_and_bearish_different(self):
        """利好和利空擴展結果應該不同。"""
        bullish = _enrich_query_directional("利好")
        bearish = _enrich_query_directional("利空")
        assert bullish != bearish

    def test_neutral_query_gets_generic_context(self):
        """中性查詢用通用擴展。"""
        result = _enrich_query_directional("A股市場")
        assert "財經新聞" in result
        # 不應注入方向特徵詞
        assert "政策落地" not in result
        assert "業績下滑" not in result

    def test_long_query_not_enriched(self):
        """長查詢（>=30字）不擴展。"""
        long_query = "半導體行業利好政策落地業績超預期技術突破量產資金持續流入訂單增長行業景氣改善"
        result = _enrich_query_directional(long_query)
        assert result == long_query

    def test_bullish_and_bearish_both_present(self):
        """同時含利好利空關鍵詞時用通用擴展。"""
        result = _enrich_query_directional("利好利空")
        assert "財經新聞" in result
        # 不應注入單一方向特徵詞
        assert "政策落地" not in result
        assert "業縟下滑" not in result

    def test_multiple_bullish_keywords(self):
        """多個利好關鍵詞都能觸發利好擴展。"""
        for kw in ["上漲", "反彈", "突破", "超預期", "增長", "景氣", "復甦"]:
            result = _enrich_query_directional(kw)
            assert "政策落地" in result or "業績超預期" in result or "資金流入" in result, f"關鍵詞「{kw}」未觸發利好擴展"

    def test_multiple_bearish_keywords(self):
        """多個利空關鍵詞都能觸發利空擴展。"""
        for kw in ["下跌", "暴跌", "暴雷", "虧損", "下滑", "收緊", "風險"]:
            result = _enrich_query_directional(kw)
            assert "業績下滑" in result or "虧損" in result or "風險事件" in result, f"關鍵詞「{kw}」未觸發利空擴展"
