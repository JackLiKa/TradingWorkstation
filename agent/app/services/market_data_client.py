"""實時金融數據客戶端 — 從公共 API 抓取大盤指數、板塊行情、財經新聞。

數據源:
1. 新浪財經 hq.sinajs.cn — 大盤指數實時行情
2. 騰訊財經 qt.gtimg.cn — 備用指數行情
3. 後端 dashboard API — 數據庫中的股票統計
4. 後端 sector-performance API — 多日板塊表現（10日行情分析）
5. 東方財富 np-listapi.eastmoney.com — 財經新聞抓取

所有數據源都是公共免費 API，無需 API Key。
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger("agent.market_data")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

# 新浪指數代碼
_INDEX_CODES = {
    "sh000001": "上證指數",
    "sz399001": "深證成指",
    "sz399006": "創業板指",
    "sh000300": "滬深300",
    "sh000016": "上證50",
    "sh000905": "中證500",
}


class MarketDataClient:
    """實時金融數據客戶端 — 從公共免費 API 抓取大盤指數和板塊行情。

    數據源包括新浪財經（指數實時行情）和騰訊財經（板塊漲跌排行），
    同時整合後端 dashboard API 的數據庫統計數據。
    """

    async def get_market_overview(self) -> dict[str, Any]:
        """獲取全市場概覽：大盤指數 + 後端統計 + 市場形態 + 廣度/輪動 + 板塊 + 新聞。

        Returns:
            {
                "indices": [{"name": "上證指數", "code": "sh000001", "price": 3990.3, "change_pct": 0.19}, ...],
                "db_stats": {...},  # 來自後端 dashboard
                "regime": {...},    # 市場形態識別結果
                "market_breadth": {...},  # 綜合/規模/風格廣度（10大類指數）
                "rotation": {...},  # 行業與風格輪動信號
                "sector_performance": [...],  # 多日板塊表現（10日）
                "news": [...],  # 財經新聞列表
                "timestamp": "2026-08-18 22:30:00",
            }
        """
        indices = await self._get_indices_sina()

        # 嘗試從後端獲取 DB 統計
        db_stats = {}
        try:
            from app.services.backend_client import backend_client

            db_stats = await backend_client.get_market_overview()
        except Exception as e:
            logger.warning(f"後端 dashboard 數據獲取失敗: {e}")

        # 獲取多日指數歷史 + 計算市場形態（一次批量調用）
        regime = await self._compute_market_regime()

        # 獲取市場廣度與輪動信號（後端緩存）
        market_breadth = await self._get_market_breadth(10)
        rotation = await self._get_rotation_signals(10)

        # 獲取多日板塊表現（10日）
        sector_performance = await self._get_sector_performance_multi_day(10)

        # 獲取財經新聞
        news = await self._get_market_news()

        return {
            "indices": indices,
            "db_stats": db_stats,
            "regime": regime,
            "market_breadth": market_breadth,
            "rotation": rotation,
            "sector_performance": sector_performance,
            "news": news,
            "timestamp": _now_str(),
        }

    async def _compute_market_regime(self) -> dict[str, Any]:
        """計算市場形態識別結果（基於多日指數歷史）。

        形態類型:
        - trending_up: 上漲趨勢（連續上漲，回撤小）
        - trending_down: 下跌趨勢（連續下跌，反彈小）
        - oscillation: 震盪行情（漲跌交替，幅度有限）
        - continuation_up: 上漲中繼（上漲後小幅回調，可能繼續上漲）
        - continuation_down: 下跌中繼（下跌後小幅反彈，可能繼續下跌）
        - unknown: 數據不足

        Returns:
            dict: 形態識別結果，含 regime_type, description, multi_day_data
        """
        try:
            from app.services.backend_client import backend_client

            # 獲取多個指數最近 10 日歷史（批量調用，減少 API 請求）
            # 數據庫中指數代碼格式為 sh.000001（帶點）
            primary_codes = ["sh.000001", "sz.399001", "sh.000300"]
            batch = await backend_client.get_index_history_batch(primary_codes, days=10)
            history = []
            used_code = ""
            for code in primary_codes:
                h = batch.get(code, [])
                if len(h) >= 3:
                    history = h
                    used_code = code
                    break
                logger.warning(f"指數 {code} 歷史數據不足 ({len(h)} 條)，嘗試下一個")

            # 主力指數都失敗時，從 index_metadata 表獲取更多指數嘗試
            if len(history) < 3:
                logger.info("主力指數數據不足，從 index_metadata 獲取更多指數嘗試")
                metadata = await backend_client.get_index_list("scale")
                fallback_codes = [item.get("code", "") for item in metadata if item.get("code") not in primary_codes]
                fallback_batch = await backend_client.get_index_history_batch(fallback_codes[:20], days=10)
                for code, h in fallback_batch.items():
                    if len(h) >= 3:
                        used_code = code
                        history = h
                        logger.info(f"從 metadata 找到可用指數: {code}")
                        break

            if len(history) < 3:
                logger.warning("所有指數都數據不足，無法計算市場形態")
                return {"regime_type": "unknown", "description": "歷史數據不足（所有指數均無足夠數據）", "multi_day_data": []}

            logger.info(f"使用指數 {used_code} 計算市場形態（{len(history)} 條歷史數據）")

            # 計算形態特徵
            changes = [h.get("pctChange", 0) or 0 for h in history]
            closes = [h.get("closePrice", 0) or 0 for h in history]

            # 漲跌交替次數
            alternations = 0
            for i in range(1, len(changes)):
                if changes[i] * changes[i - 1] < 0:  # 符號相反
                    alternations += 1

            # 累計漲幅
            total_change = sum(changes)
            # 平均絕對漲跌幅
            avg_abs_change = sum(abs(c) for c in changes) / len(changes)
            # 最大單日漲幅/跌幅
            max_change = max(changes) if changes else 0
            min_change = min(changes) if changes else 0
            # 波動率（標準差）
            if len(changes) > 1:
                mean_change = sum(changes) / len(changes)
                variance = sum((c - mean_change) ** 2 for c in changes) / len(changes)
                volatility = variance**0.5
            else:
                volatility = 0

            # 價格趨勢（首尾對比）
            if closes[0] and closes[-1]:
                price_change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100
            else:
                price_change_pct = 0

            # === 形態判定邏輯 ===
            alternation_ratio = alternations / (len(changes) - 1) if len(changes) > 1 else 0

            regime_type = "unknown"
            description = ""

            if alternation_ratio >= 0.6 and avg_abs_change < 1.5:
                # 漲跌交替頻繁 + 幅度小 → 震盪
                regime_type = "oscillation"
                description = (
                    f"最近{len(changes)}日漲跌交替{alternations}次（交替率{alternation_ratio:.0%}），"
                    f"平均幅度{avg_abs_change:.2f}%，呈現震盪格局。"
                    f"累計{total_change:+.2f}%，波動率{volatility:.2f}%。"
                )
            elif total_change > 3 and alternation_ratio < 0.3:
                # 累計上漲 + 很少交替 → 上漲趨勢
                regime_type = "trending_up"
                description = (
                    f"最近{len(changes)}日累計上漲{total_change:+.2f}%，交替僅{alternations}次，呈現上漲趨勢。"
                )
            elif total_change < -3 and alternation_ratio < 0.3:
                # 累計下跌 + 很少交替 → 下跌趨勢
                regime_type = "trending_down"
                description = (
                    f"最近{len(changes)}日累計下跌{total_change:+.2f}%，交替僅{alternations}次，呈現下跌趨勢。"
                )
            elif total_change > 1 and alternation_ratio >= 0.3 and alternation_ratio < 0.6:
                # 上漲但有一定回調 → 上漲中繼
                regime_type = "continuation_up"
                description = (
                    f"最近{len(changes)}日累計{total_change:+.2f}%，"
                    f"有{alternations}次回調（交替率{alternation_ratio:.0%}），"
                    f"可能是上漲中繼，短期回調後或繼續上漲。"
                )
            elif total_change < -1 and alternation_ratio >= 0.3 and alternation_ratio < 0.6:
                # 下跌但有一定反彈 → 下跌中繼
                regime_type = "continuation_down"
                description = (
                    f"最近{len(changes)}日累計{total_change:+.2f}%，"
                    f"有{alternations}次反彈（交替率{alternation_ratio:.0%}），"
                    f"可能是下跌中繼，短期反彈後或繼續下跌。"
                )
            else:
                regime_type = "oscillation"
                description = (
                    f"最近{len(changes)}日累計{total_change:+.2f}%，"
                    f"交替{alternations}次，平均幅度{avg_abs_change:.2f}%，"
                    f"暫無明確趨勢，偏震盪。"
                )

            # 構建多日數據摘要（供 prompt 注入）
            multi_day_data = []
            for h in history:
                multi_day_data.append(
                    {
                        "date": str(h.get("tradeDate", "")),
                        "close": h.get("closePrice", 0),
                        "pct_chg": h.get("pctChange", 0),
                    }
                )

            return {
                "regime_type": regime_type,
                "description": description,
                "multi_day_data": multi_day_data,
                "metrics": {
                    "total_change": round(total_change, 2),
                    "avg_abs_change": round(avg_abs_change, 2),
                    "max_change": round(max_change, 2),
                    "min_change": round(min_change, 2),
                    "volatility": round(volatility, 2),
                    "alternations": alternations,
                    "alternation_ratio": round(alternation_ratio, 2),
                    "price_change_pct": round(price_change_pct, 2),
                    "days_analyzed": len(changes),
                },
            }
        except Exception as e:
            logger.warning(f"市場形態計算失敗: {e}")
            return {"regime_type": "unknown", "description": "計算失敗", "multi_day_data": []}

    async def _get_indices_sina(self) -> list[dict[str, Any]]:
        """從新浪財經獲取大盤指數實時行情。

        新浪 API 返回格式為 var hq_str_sh000001="名稱,昨收,今收,...",
        本方法解析每行並計算漲跌幅。

        Returns:
            list[dict]: 指數行情列表，每項含 name / code / price / change_pct；
                        獲取失敗時返回空列表
        """
        codes = ",".join(_INDEX_CODES.keys())
        try:
            async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
                resp = await client.get(f"https://hq.sinajs.cn/list={codes}")
                resp.raise_for_status()
                # 新浪返回 var hq_str_sh000001="上證指數,3979.49,3982.65,3990.30,..."
                lines = resp.text.strip().split("\n")
                indices = []
                for line in lines:
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    code_part = line.split("=")[0].split("_")[-1]
                    data_part = line.split('"')[1] if '"' in line else ""
                    fields = data_part.split(",")
                    if len(fields) < 4:
                        continue
                    name = fields[0]
                    preclose = _safe_float(fields[2])
                    current = _safe_float(fields[3])
                    change_pct = ((current - preclose) / preclose * 100) if preclose else 0
                    indices.append(
                        {
                            "name": name,
                            "code": code_part,
                            "price": current,
                            "preclose": preclose,
                            "change_pct": round(change_pct, 2),
                        }
                    )
                logger.info(f"獲取 {len(indices)} 個指數行情")
                return indices
        except Exception as e:
            logger.warning(f"新浪指數獲取失敗: {e}")
            return []

    async def get_sector_performance(self) -> list[dict[str, Any]]:
        """獲取行業板塊漲跌幅排行（從騰訊財經）。

        Returns:
            [{"sector": "半導體", "change_pct": 3.5, "leader": "xxx"}, ...]
        """
        # 騰訊板塊 API
        try:
            async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
                resp = await client.get(
                    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/rankBK/getBKRank",
                    params={"type": "industry", "sort": "3", "page": "0", "num": "20"},
                )
                resp.raise_for_status()
                data = resp.json()
                sectors = []
                for item in data.get("data", {}).get("rankBK", [])[:20]:
                    sectors.append(
                        {
                            "sector": item.get("name", ""),
                            "change_pct": _safe_float(item.get("changePct", 0)),
                            "leader": item.get("leaderName", ""),
                        }
                    )
                logger.info(f"獲取 {len(sectors)} 個行業板塊")
                return sectors
        except Exception as e:
            logger.warning(f"騰訊板塊數據獲取失敗: {e}")
            return []

    async def _get_sector_performance_multi_day(self, days: int = 10) -> list[dict[str, Any]]:
        """從後端獲取多日板塊表現（各行業平均漲跌幅 + 領漲股）。

        用於 10 日行情分析，識別利好/利空行業及其延續性。

        Args:
            days: 最近交易日天數

        Returns:
            list[dict]: 板塊表現列表，每項含 date/industry/avgPctChange/topCode/topCodeName/topPctChange
        """
        try:
            from app.services.backend_client import backend_client

            data = await backend_client.get_sector_performance(days)
            logger.info(f"獲取 {len(data)} 條板塊表現數據（{days}日）")
            return data
        except Exception as e:
            logger.warning(f"多日板塊表現獲取失敗: {e}")
            return []

    async def _get_market_breadth(self, days: int = 10) -> dict[str, Any]:
        """從後端獲取市場廣度分析（綜合/規模/風格/行業）。

        基於 index_metadata 中 10 大類別 ~80 個指數計算，走後端 Caffeine 緩存。

        Args:
            days: 最近交易日天數

        Returns:
            dict: 市場廣度 DTO
        """
        try:
            from app.services.backend_client import backend_client

            data = await backend_client.get_market_breadth(days)
            logger.info(f"獲取市場廣度（{days}日）: {data.get('summary', '')[:60]}...")
            return data
        except Exception as e:
            logger.warning(f"市場廣度獲取失敗: {e}")
            return {}

    async def _get_rotation_signals(self, days: int = 10) -> dict[str, Any]:
        """從後端獲取輪動信號分析（行業與風格輪動）。

        基於一級/二級行業指數和成長/價值指數計算，走後端 Caffeine 緩存。

        Args:
            days: 最近交易日天數

        Returns:
            dict: 輪動信號 DTO
        """
        try:
            from app.services.backend_client import backend_client

            data = await backend_client.get_rotation_signals(days)
            logger.info(f"獲取輪動信號（{days}日）: rotationStrength={data.get('rotationStrength', 0)}")
            return data
        except Exception as e:
            logger.warning(f"輪動信號獲取失敗: {e}")
            return {}

    async def _get_market_news(self, page_size: int = 20) -> list[dict[str, Any]]:
        """從東方財經抓取最新財經新聞（A股市場要聞）。

        東方財富 API 返回 JSON 格式的市場要聞列表，無需 API Key。

        Args:
            page_size: 抓取新聞條數（默認 20）

        Returns:
            list[dict]: 新聞列表，每項含 title/source/date/url
        """
        try:
            async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
                # 東方財富市場要聞 API（column=350 為市場頻道）
                resp = await client.get(
                    "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns",
                    params={
                        "client": "web",
                        "biz": "web_news_col",
                        "column": "350",
                        "order": 1,
                        "needInteract": 0,
                        "pageSize": page_size,
                        "pageNo": 1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                news_list = []
                for item in data.get("data", {}).get("list", [])[:page_size]:
                    news_list.append(
                        {
                            "title": item.get("Art_Title", ""),
                            "source": "東方財富",
                            "date": item.get("Art_ShowTime", "")[:10] if item.get("Art_ShowTime") else "",
                            "url": f"https://finance.eastmoney.com/a/{item.get('Art_Code', '')}.html",
                        }
                    )
                logger.info(f"獲取 {len(news_list)} 條財經新聞")
                return news_list
        except Exception as e:
            logger.warning(f"東方財富新聞抓取失敗: {e}")
            return []

    async def search_news_by_keyword(self, keyword: str, page_size: int = 10) -> list[dict[str, Any]]:
        """按關鍵詞搜索財經新聞（用於利好/利空方向的新聞追蹤）。

        使用東方財富搜索 API，查找與特定行業/關鍵詞相關的新聞。

        Args:
            keyword: 搜索關鍵詞（如「半導體」「新能源」「房地產」）
            page_size: 返回新聞條數

        Returns:
            list[dict]: 新聞列表，每項含 title/source/date/url
        """
        try:
            async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
                resp = await client.get(
                    "https://search-api-web.eastmoney.com/search/jsonp",
                    params={
                        "cb": "jQuery",
                        "param": f'{{"uid":"","keyword":"{keyword}","type":["cmsArticleWebOld"],"client":"web","clientType":"web","clientVersion":"curr","param":{{"cmsArticleWebOld":{{"searchScope":"default","sort":"default","pageIndex":1,"pageSize":{page_size},"preTag":"<em>","postTag":"</em>"}}}}}}',
                    },
                )
                resp.raise_for_status()
                # JSONP 格式，需要去除回調函數包裝
                text = resp.text
                start = text.find("(")
                end = text.rfind(")")
                if start == -1 or end == -1:
                    return []
                json_str = text[start + 1 : end]
                import json

                data = json.loads(json_str)
                news_list = []
                articles = (
                    data.get("result", {})
                    .get("cmsArticleWebOld", {})
                    .get("list", [])
                )
                for item in articles[:page_size]:
                    news_list.append(
                        {
                            "title": item.get("title", "").replace("<em>", "").replace("</em>", ""),
                            "source": item.get("mediaName", "東方財富"),
                            "date": item.get("date", "")[:10] if item.get("date") else "",
                            "url": item.get("url", ""),
                        }
                    )
                logger.info(f"搜索關鍵詞「{keyword}」獲取 {len(news_list)} 條新聞")
                return news_list
        except Exception as e:
            logger.warning(f"按關鍵詞「{keyword}」搜索新聞失敗: {e}")
            return []


def _safe_float(val) -> float:
    """安全轉換為 float，轉換失敗時返回 0.0。

    Args:
        val: 待轉換的值（可能是字符串、數字或 None）

    Returns:
        float: 轉換後的浮點數，失敗時為 0.0
    """
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _now_str() -> str:
    """獲取當前時間的字符串表示（格式 YYYY-MM-DD HH:MM:SS）。

    Returns:
        str: 當前本地時間字符串
    """
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 全局市場數據客戶端單例
market_data_client = MarketDataClient()
