"""實時金融數據客戶端 — 從公共 API 抓取大盤指數、板塊行情、財經新聞。

數據源:
1. 新浪財經 hq.sinajs.cn — 大盤指數實時行情
2. 騰訊財經 qt.gtimg.cn — 備用指數行情
3. 後端 dashboard API — 數據庫中的股票統計
4. 後端 sector-performance API — 多日板塊表現（10日行情分析）
5. 後端 industry-daily API — 行業日聚合（行業漲跌/成交/漲跌家數）
6. 東方財富 np-listapi.eastmoney.com — 財經新聞抓取

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
                "industry_daily": [...],  # 最新交易日行業聚合（漲跌/成交/家數）
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

        # 獲取最新交易日行業聚合
        industry_daily = await self._get_industry_daily()

        # 獲取財經新聞
        news = await self._get_market_news()

        return {
            "indices": indices,
            "db_stats": db_stats,
            "regime": regime,
            "market_breadth": market_breadth,
            "rotation": rotation,
            "sector_performance": sector_performance,
            "industry_daily": industry_daily,
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

    async def _get_industry_daily(self, trade_date: str = None) -> list[dict[str, Any]]:
        """從後端獲取行業日聚合數據（行業漲跌/成交/漲跌家數）。

        用於識別當日強弱行業、行業熱度與資金流向。

        Args:
            trade_date: 交易日期 YYYY-MM-DD，為空時使用最新交易日

        Returns:
            list[dict]: 行業聚合列表，每項含 tradeDate/industry/avgPctChg/
                        totalAmount/risingCount/fallingCount/stockCount 等
        """
        try:
            from app.services.backend_client import backend_client

            data = await backend_client.get_industry_daily(trade_date)
            logger.info(f"獲取 {len(data)} 條行業日聚合數據")
            return data
        except Exception as e:
            logger.warning(f"行業日聚合獲取失敗: {e}")
            return []

    async def _get_industry_daily_range(self, industry: str, start: str, end: str) -> list[dict[str, Any]]:
        """從後端獲取指定行業在日期區間內的聚合數據。"""
        try:
            from app.services.backend_client import backend_client

            data = await backend_client.get_industry_daily_range(industry, start, end)
            logger.info(f"獲取 {industry} 區間 {start}~{end} 共 {len(data)} 條")
            return data
        except Exception as e:
            logger.warning(f"行業區間聚合獲取失敗: {e}")
            return []

    async def get_industry_prosperity(self) -> dict[str, Any]:
        """獲取行業景氣度指標，格式化為 prompt 可注入文本。

        用於 Agent 策略生成時參考景氣度評分選擇行業。

        Returns:
            dict: {
                "top_prosperous": [{"industry": ..., "index": ..., "grade": ...}, ...],
                "bottom_prosperous": [...],
                "text": "可注入 prompt 的文本摘要",
            }
        """
        try:
            from app.services.backend_client import backend_client

            data = await backend_client.get_industry_prosperity()
            if not data:
                return {"top_prosperous": [], "bottom_prosperous": [], "text": ""}

            # 取景氣度最高和最低的各 10 個行業
            top = data[:10]
            bottom = data[-10:] if len(data) >= 10 else []

            top_list = [
                {
                    "industry": d.get("industry", ""),
                    "index": d.get("prosperityIndex", 0),
                    "grade": d.get("grade", ""),
                    "avgPctChg": d.get("avgPctChg", 0),
                }
                for d in top
            ]
            bottom_list = [
                {
                    "industry": d.get("industry", ""),
                    "index": d.get("prosperityIndex", 0),
                    "grade": d.get("grade", ""),
                    "avgPctChg": d.get("avgPctChg", 0),
                }
                for d in bottom
            ]

            # 構建 prompt 文本
            lines = ["## 行業景氣度指標（綜合評分，0-100）"]
            lines.append("評分維度：動量(漲跌幅,35%) + 資金(成交額,25%) + 活躍(換手率,20%) + 廣度(漲跌家數比,20%)")
            lines.append("等級：繁榮(≥80) / 景氣(≥65) / 平穩(≥50) / 低迷(≥35) / 衰退(<35)")
            lines.append("")
            lines.append("### 景氣度最高行業（建議優先聚焦）")
            for d in top:
                lines.append(
                    f"- {d.get('industry', '')}: 景氣度 {d.get('prosperityIndex', 0):.1f} "
                    f"({d.get('grade', '')}), 漲跌幅 {d.get('avgPctChg', 0):.3f}%"
                )
            if bottom:
                lines.append("")
                lines.append("### 景氣度最低行業（建議避開）")
                for d in bottom:
                    lines.append(
                        f"- {d.get('industry', '')}: 景氣度 {d.get('prosperityIndex', 0):.1f} "
                        f"({d.get('grade', '')}), 漲跌幅 {d.get('avgPctChg', 0):.3f}%"
                    )
            lines.append("")
            lines.append("建議：若需聚焦行業，優先選擇景氣度 ≥ 65 的「繁榮」或「景氣」等級行業；避免選擇「低迷」或「衰退」等級行業。")

            text = "\n".join(lines)
            logger.info(f"行業景氣度獲取完成: top={len(top_list)}, bottom={len(bottom_list)}")
            return {
                "top_prosperous": top_list,
                "bottom_prosperous": bottom_list,
                "text": text,
            }
        except Exception as e:
            logger.warning(f"行業景氣度獲取失敗: {e}")
            return {"top_prosperous": [], "bottom_prosperous": [], "text": ""}

    async def get_rotation_prediction(self, lookback_days: int = 20) -> dict[str, Any]:
        """獲取行業輪動預測，格式化為 prompt 可注入文本。

        用於 Agent 策略生成時參考輪動預測選擇行業。

        Args:
            lookback_days: 回溯天數（默認 20）

        Returns:
            dict: {
                "predicted_leaders": [...],
                "predicted_laggards": [...],
                "confidence": float,
                "text": "可注入 prompt 的文本摘要",
            }
        """
        try:
            from app.services.backend_client import backend_client

            data = await backend_client.get_rotation_prediction(lookback_days)
            if not data:
                return {"predicted_leaders": [], "predicted_laggards": [], "confidence": 0.0, "text": ""}

            leaders = data.get("predictedLeaders", [])
            laggards = data.get("predictedLaggards", [])
            confidence = data.get("confidence", 0.0)

            lines = ["## 行業輪動預測"]
            lines.append(f"預測信心度：{confidence:.1f}%")
            lines.append("以下行業預測為下一輪領漲（綜合動量+資金+趨勢評分）：")
            for ind in leaders[:5]:
                lines.append(
                    f"- {ind.get('industry', '')}: 評分 {ind.get('score', 0):.1f} "
                    f"(動量{ind.get('momentumScore', 0):.0f}/資金{ind.get('capitalScore', 0):.0f}/趨勢{ind.get('trendScore', 0):.0f})"
                )
            if laggards:
                lines.append("")
                lines.append("以下行業預測為下一輪滯後（建議避開）：")
                for ind in laggards[:3]:
                    lines.append(
                        f"- {ind.get('industry', '')}: 評分 {ind.get('score', 0):.1f}"
                    )
            lines.append("")
            lines.append("建議：可參考輪動預測選擇行業聚焦，優先考慮預測領漲的行業。")

            text = "\n".join(lines)
            logger.info(f"輪動預測獲取完成: leaders={len(leaders)}, confidence={confidence:.1f}%")
            return {
                "predicted_leaders": leaders,
                "predicted_laggards": laggards,
                "confidence": confidence,
                "text": text,
            }
        except Exception as e:
            logger.warning(f"輪動預測獲取失敗: {e}")
            return {"predicted_leaders": [], "predicted_laggards": [], "confidence": 0.0, "text": ""}

    async def get_capital_migration(self, days: int = 10) -> dict[str, Any]:
        """計算行業間資金流向遷移（首尾交易日成交金額佔比變化）。

        用於 Agent 策略生成時參考資金遷移方向選擇行業。

        Args:
            days: 回溯天數（默認 10 日）

        Returns:
            dict: {
                "inflow_industries": [{"industry": ..., "change": ..., "amount": ...}, ...],
                "outflow_industries": [...],
                "text": "可注入 prompt 的文本摘要",
            }
        """
        try:
            from datetime import datetime, timedelta
            from app.services.backend_client import backend_client

            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
            data = await backend_client.get_all_industry_daily_range(start, end)
            if not data or len(data) < 10:
                return {"inflow_industries": [], "outflow_industries": [], "text": ""}

            # 按日期分組
            by_date: dict[str, dict[str, float]] = {}
            for item in data:
                ind = item.get("industry", "")
                amt = item.get("totalAmount")
                date = item.get("tradeDate", "")
                if not ind or amt is None or not date:
                    continue
                if date not in by_date:
                    by_date[date] = {}
                by_date[date][ind] = float(amt)

            sorted_dates = sorted(by_date.keys())
            if len(sorted_dates) < 2:
                return {"inflow_industries": [], "outflow_industries": [], "text": ""}

            first_date = sorted_dates[0]
            last_date = sorted_dates[-1]
            first_data = by_date[first_date]
            last_data = by_date[last_date]

            first_total = sum(first_data.values())
            last_total = sum(last_data.values())
            if first_total == 0 or last_total == 0:
                return {"inflow_industries": [], "outflow_industries": [], "text": ""}

            # 計算各行業佔比變化
            all_industries = set(first_data.keys()) | set(last_data.keys())
            flow_list = []
            for ind in all_industries:
                first_share = first_data.get(ind, 0) / first_total
                last_share = last_data.get(ind, 0) / last_total
                change = last_share - first_share
                flow_list.append({
                    "industry": ind,
                    "change": change,
                    "first_amount": first_data.get(ind, 0) / 1e8,
                    "last_amount": last_data.get(ind, 0) / 1e8,
                })

            # 取流入/流出 Top 10
            inflow = sorted([f for f in flow_list if f["change"] > 0], key=lambda x: x["change"], reverse=True)[:10]
            outflow = sorted([f for f in flow_list if f["change"] < 0], key=lambda x: x["change"])[:10]

            # 構建 prompt 文本
            lines = ["## 行業資金流向遷移分析"]
            lines.append(f"比較區間：{first_date} → {last_date}")
            lines.append("以下行業成交金額佔比上升（資金流入），可能是市場資金正在追捧的方向：")
            for f in inflow[:5]:
                lines.append(
                    f"- {f['industry']}: 佔比變化 +{f['change']*100:.2f}%，"
                    f"成交額 {f['first_amount']:.1f}億 → {f['last_amount']:.1f}億"
                )
            if outflow:
                lines.append("")
                lines.append("以下行業成交金額佔比下降（資金流出），可能是市場資金正在撤離的方向：")
                for f in outflow[:5]:
                    lines.append(
                        f"- {f['industry']}: 佔比變化 {f['change']*100:.2f}%，"
                        f"成交額 {f['first_amount']:.1f}億 → {f['last_amount']:.1f}億"
                    )
            lines.append("")
            lines.append("建議：若需聚焦行業，優先考慮資金持續流入的行業；避免資金持續流出的行業。")

            text = "\n".join(lines)
            logger.info(f"資金遷移計算完成: inflow={len(inflow)}, outflow={len(outflow)}")
            return {
                "inflow_industries": inflow,
                "outflow_industries": outflow,
                "text": text,
            }
        except Exception as e:
            logger.warning(f"資金遷移計算失敗: {e}")
            return {"inflow_industries": [], "outflow_industries": [], "text": ""}

    async def get_industry_correlation(self, days: int = 30) -> dict[str, Any]:
        """計算行業間相關性矩陣，識別高相關行業對。

        用於 Agent 策略生成時避免高相關行業過度集中。

        Args:
            days: 回溯天數（默認 30 日）

        Returns:
            dict: {
                "high_corr_pairs": [{"a": indA, "b": indB, "corr": 0.85}, ...],
                "industry_groups": [[ind1, ind2, ...], ...],  # 高相關行業聚類
                "text": "可注入 prompt 的文本摘要",
            }
        """
        try:
            from datetime import datetime, timedelta
            from app.services.backend_client import backend_client

            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
            data = await backend_client.get_all_industry_daily_range(start, end)
            if not data or len(data) < 10:
                return {"high_corr_pairs": [], "industry_groups": [], "text": ""}

            # 按行業分組
            industry_map: dict[str, dict[str, float]] = {}
            for item in data:
                ind = item.get("industry", "")
                pct = item.get("avgPctChg")
                date = item.get("tradeDate", "")
                if not ind or pct is None or not date:
                    continue
                if ind not in industry_map:
                    industry_map[ind] = {}
                industry_map[ind][date] = float(pct)

            if len(industry_map) < 2:
                return {"high_corr_pairs": [], "industry_groups": [], "text": ""}

            # 取波動率最大的 20 個行業
            volatility_list = []
            for ind, series in industry_map.items():
                values = list(series.values())
                if len(values) < 5:
                    continue
                mean = sum(values) / len(values)
                variance = sum((v - mean) ** 2 for v in values) / len(values)
                volatility_list.append((ind, variance ** 0.5, values, list(series.keys())))
            volatility_list.sort(key=lambda x: x[1], reverse=True)
            selected = volatility_list[:20]

            if len(selected) < 2:
                return {"high_corr_pairs": [], "industry_groups": [], "text": ""}

            # 對齊日期
            all_dates = set()
            for s in selected:
                all_dates.update(s[3])
            sorted_dates = sorted(all_dates)

            # 構建序列矩陣
            series_data = []
            for s in selected:
                date_map = dict(zip(s[3], s[2]))
                series_data.append([date_map.get(d, 0.0) for d in sorted_dates])

            # 計算 Pearson 相關係數
            n = len(selected)
            corr_matrix = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(n):
                    if i == j:
                        corr_matrix[i][j] = 1.0
                    elif j > i:
                        corr = _pearson_corr(series_data[i], series_data[j])
                        corr_matrix[i][j] = corr
                        corr_matrix[j][i] = corr

            # 找出高相關行業對（>= 0.7）
            high_corr_pairs = []
            for i in range(n):
                for j in range(i + 1, n):
                    if corr_matrix[i][j] >= 0.7:
                        high_corr_pairs.append({
                            "a": selected[i][0],
                            "b": selected[j][0],
                            "corr": round(corr_matrix[i][j], 3),
                        })
            high_corr_pairs.sort(key=lambda x: x["corr"], reverse=True)

            # 構建行業聚類（簡單貪心：高相關的行業歸為一組）
            industry_groups = _build_correlation_groups(high_corr_pairs)

            # 構建 prompt 文本
            text_lines = []
            if high_corr_pairs:
                text_lines.append("## 行業相關性分析（避免高相關行業過度集中）")
                text_lines.append("以下行業對走勢高度相關（相關係數 ≥ 0.7），若在 industries 中同時選擇會降低分散度：")
                for pair in high_corr_pairs[:8]:
                    text_lines.append(f"- {pair['a']} × {pair['b']} (相關係數 {pair['corr']})")
                if industry_groups:
                    text_lines.append("")
                    text_lines.append("高相關行業聚類（同組行業不宜同時聚焦）：")
                    for i, group in enumerate(industry_groups[:5], 1):
                        text_lines.append(f"  組{i}: {', '.join(group)}")
                text_lines.append("")
                text_lines.append("建議：若需聚焦多個行業，優先選擇不同聚類組的行業，提升組合分散度。")
            text = "\n".join(text_lines)

            logger.info(f"行業相關性計算完成: {len(high_corr_pairs)} 個高相關對, {len(industry_groups)} 個聚類組")
            return {
                "high_corr_pairs": high_corr_pairs,
                "industry_groups": industry_groups,
                "text": text,
            }
        except Exception as e:
            logger.warning(f"行業相關性計算失敗: {e}")
            return {"high_corr_pairs": [], "industry_groups": [], "text": ""}

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


def _pearson_corr(x: list[float], y: list[float]) -> float:
    """計算兩個序列的 Pearson 相關係數。"""
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    sx = x[:n]
    sy = y[:n]
    mean_x = sum(sx) / n
    mean_y = sum(sy) / n
    num = sum((sx[i] - mean_x) * (sy[i] - mean_y) for i in range(n))
    dx = sum((v - mean_x) ** 2 for v in sx)
    dy = sum((v - mean_y) ** 2 for v in sy)
    denom = (dx * dy) ** 0.5
    if denom == 0:
        return 0.0
    return num / denom


def _build_correlation_groups(high_corr_pairs: list[dict]) -> list[list[str]]:
    """根據高相關行業對構建聚類組（簡單貪心 union-find）。

    Args:
        high_corr_pairs: 高相關行業對列表，每項含 a/b/corr

    Returns:
        list[list[str]]: 聚類組列表，每組為高相關行業名稱列表
    """
    parent: dict[str, str] = {}

    def find(s: str) -> str:
        if s not in parent:
            parent[s] = s
            return s
        while parent[s] != s:
            parent[s] = parent[parent[s]]
            s = parent[s]
        return s

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for pair in high_corr_pairs:
        union(pair["a"], pair["b"])

    groups_map: dict[str, list[str]] = {}
    for s in parent:
        root = find(s)
        groups_map.setdefault(root, []).append(s)

    # 只保留長度 >= 2 的組
    groups = [sorted(g) for g in groups_map.values() if len(g) >= 2]
    groups.sort(key=lambda g: len(g), reverse=True)
    return groups


def _now_str() -> str:
    """獲取當前時間的字符串表示（格式 YYYY-MM-DD HH:MM:SS）。

    Returns:
        str: 當前本地時間字符串
    """
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 全局市場數據客戶端單例
market_data_client = MarketDataClient()
