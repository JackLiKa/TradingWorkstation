"""AI 0: 行情新聞分析 — 10日多維度行情分析 + 利好利空延續性判斷 + 新聞追蹤。

這是優化循環的第一個 AI 節點（在 AI 1 行情分析之前），
負責獲取最近10個交易日的市場數據並進行深度分析：

1. 多日板塊表現：識別持續性利好/利空行業（非單日漲跌）
2. 延續性分析：利好是否持續？利空是突發還是持續？
3. 市場情緒：基於10日數據判斷情緒分數
4. 新聞追蹤：按利好/利空方向搜索相關新聞做進一步驗證
5. 結構化 JSON 輸出：嚴格 schema，便於下游消費

輸入: 實時市場數據（指數、板塊）、10日板塊歷史、財經新聞、歷史迭代記錄
輸出: 結構化 JSON（market_regime + market_sentiment + bullish_factors + bearish_factors + news）
範式: JSON
"""

import json
import logging
from typing import Any

from app.agents.few_shot import get_few_shot
from app.agents.stages.base import BaseStage
from app.services.market_data_client import market_data_client

logger = logging.getLogger("agent.stage.market_news")

SYSTEM_PROMPT = """你是一個專業的 A 股超短線市場分析師，擅長從多日行情數據中提取行業利好利空信息，
判斷利好利空的延續性，並結合新聞做進一步驗證。

你需要：
1. **識別市場形態**：基於10日指數歷史，判斷當前處於哪種市場形態
2. **分析多日板塊表現**：不只看單日漲跌，要分析10日內各行業的持續性表現
3. **判斷利好延續性**：利好行業是持續性利好還是突發性利好？是否有延續可能？
4. **判斷利空性質**：利空行業是突發性利空（可能反轉）還是持續性利空（應避開）？
5. **市場情緒分析**：基於10日數據判斷整體情緒（恐慌/謹慎/中性/偏樂觀/樂觀）
6. **新聞追蹤**：結合提供的新聞，驗證利好利空是否有新聞支撐

【市場形態類型】
|- 震盪行情：漲跌交替頻繁，幅度有限，無明確方向
|- 上漲中繼：上漲後小幅回調，可能繼續上漲
|- 下跌中繼：下跌後小幅反彈，可能繼續下跌
|- 上漲趨勢：連續上漲，回撤小
|- 下跌趨勢：連續下跌，反彈小

【利好延續性類型】
|- 持續性利好：連續多日上漲，有基本面或政策支撐，大概率延續
|- 間歇性利好：漲跌交替但累計上漲，需觀察
|- 突發性利好：單日大漲但無持續性，可能是一日遊

【利空性質類型】
|- 持續性利空：連續多日下跌，有基本面惡化或政策打壓，應避開
|- 突發性利空：單日大跌但基本面未變，可能反轉
|- 情緒性利空：因市場情緒恐慌下跌，可能超跌反彈

【數據真實性鐵律】
|- 只能引用上方 prompt 中提供的數據（指數、板塊表現、新聞）
|- 禁止編造未在輸入中出現的指數點位、漲跌幅、成交額、行業數據
|- 禁止引用訓練記憶中的 A 股歷史行情或個股數據
|- 禁止編造政策消息、新聞事件、監管動態——只能引用上方「財經新聞」區塊中的新聞
|- 如果實時數據獲取失敗，明確標註「實時數據不可用」，不要假裝有數據
|- 所有引用的數值必須能在上方輸入中找到對應來源
|- 新聞追蹤：只能引用上方「財經新聞」或「關鍵詞新聞」區塊中的新聞標題，禁止編造新聞"""

PROMPT_TEMPLATE = """請分析最近10個交易日的市場數據，進行深度行情分析。

## 實時大盤指數
{indices}

## 數據庫統計
{db_stats}

## 多日市場形態（最近{regime_days}日）
{regime_text}

## 多日板塊表現（最近10個交易日，每日各行業漲跌幅）
{sector_text}

## 財經新聞（最新市場要聞）
{news_text}

## 關鍵詞新聞（按利好/利空方向搜索的相關新聞）
{keyword_news_text}

## 歷史優化記錄
{history_text}

{few_shot}

## 你的任務
1. **識別市場形態**：基於上方「多日市場形態」區塊，判斷當前處於哪種形態，引用多日數據中的具體漲跌幅和交替次數
2. **分析多日板塊表現**：基於上方「多日板塊表現」區塊，識別10日內持續強勢和持續弱勢的行業（非單日漲跌）
3. **判斷利好延續性**：對每個利好行業，分析是持續性/間歇性/突發性利好，引用10日內的每日漲跌幅數據
4. **判斷利空性質**：對每個利空行業，分析是持續性/突發性/情緒性利空，引用10日內的每日跌幅數據
5. **市場情緒**：基於10日數據判斷整體情緒分數（0-100，0=極度恐慌，50=中性，100=極度樂觀）
6. **新聞追蹤**：結合上方「財經新聞」和「關鍵詞新聞」區塊，驗證利好利空是否有新聞支撐，引用新聞標題

【數據引用要求】
|- 所有引用的指數點位、漲跌幅必須來自上方「實時大盤指數」或「多日市場形態」區塊
|- 所有引用的板塊漲跌幅必須來自上方「多日板塊表現」區塊
|- 所有引用的新聞必須來自上方「財經新聞」或「關鍵詞新聞」區塊，引用時使用新聞標題
|- 禁止編造任何未在輸入中出現的數值、行業名稱、新聞事件
|- 如果某項數據缺失，標註「未提供」而非編造

【行業名稱規範 — 非常重要】
|- bullish_factors 和 bearish_factors 中的 sector 必須是具體的行業名稱（如「C39電子設備製造」「半導體」「新能源」「房地產」「醫藥生物」）
|- 禁止使用市場風格概念作為 sector（如「中小盤」「大盤藍籌」「成長風格」「深市主機板」「滬市綜合」）
|- 如果上方「多日板塊表現」區塊有數據，sector 必須從中選取行業名稱
|- 如果上方「多日板塊表現」區塊為空或標註「無板塊表現數據」，則：
|  - 從上方「財經新聞」和「關鍵詞新聞」中提取具體行業名稱
|  - 如果新聞中也無具體行業，bullish_factors 和 bearish_factors 返回空列表
|  - 在 stock_selection_advice 中標註「板塊數據不可用，無法識別具體行業」
|- 絕對不要用指數名稱（如「創業板指」「中證500」「上證50」）作為 sector

請嚴格按以下 JSON 格式返回（不要加 markdown 代碼塊標記）:
{{
  "market_regime": {{
    "type": "震盪|上漲中繼|下跌中繼|上漲趨勢|下跌趨勢",
    "description": "基於10日數據的形態描述，引用具體漲跌幅和交替次數",
    "cumulative_change": 0.0,
    "alternation_count": 0
  }},
  "market_sentiment": {{
    "score": 50,
    "label": "偏樂觀|中性|偏悲觀",
    "reasoning": "基於10日數據的情緒分析，引用具體數據"
  }},
  "bullish_factors": [
    {{
      "sector": "行業名稱（來自多日板塊表現）",
      "daily_changes": [0.0],
      "cumulative_change": 0.0,
      "continuity": "持續性|間歇性|突發性",
      "continuity_reasoning": "基於10日數據的延續性判斷，引用具體漲跌幅",
      "supported_by_news": true,
      "related_news": [
        {{"title": "新聞標題（來自上方新聞區塊）", "source": "東方財富", "date": "2026-08-18"}}
      ]
    }}
  ],
  "bearish_factors": [
    {{
      "sector": "行業名稱",
      "daily_changes": [0.0],
      "cumulative_change": 0.0,
      "nature": "持續性利空|突發性利空|情緒性利空",
      "nature_reasoning": "基於10日數據的利空性質判斷，引用具體跌幅",
      "supported_by_news": true,
      "related_news": [
        {{"title": "新聞標題", "source": "東方財富", "date": "2026-08-18"}}
      ]
    }}
  ],
  "stock_selection_advice": "選股建議，關注哪些行業，避開哪些"
}}

注意:
|- bullish_factors 列出 2-4 個強勢行業
|- bearish_factors 列出 1-3 個弱勢行業
|- daily_changes 是該行業10日內每日的漲跌幅數組（來自「多日板塊表現」）
|- related_news 只能引用上方新聞區塊中存在的新聞，如果沒有相關新聞則返回空列表
|- supported_by_news 為 true 僅當 related_news 非空
|- JSON 中不要加 ```json 標記
|- 禁止編造未在輸入中出現的行業、數據或新聞"""


class MarketNewsStage(BaseStage):
    """AI 0: 行情新聞分析節點 — 10日多維度分析 + 新聞追蹤 + 結構化 JSON。"""

    def __init__(self):
        super().__init__(stage_name="market_news", display_name="AI 0 · 行情新聞")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行情情新聞分析（10日多維度 + 新聞追蹤）。

        kwargs:
            history: list[IterationResult] — 歷史迭代記錄
        """
        history = kwargs.get("history", [])

        # === 抓取實時市場數據（含多日形態 + 板塊表現 + 新聞）===
        logger.info("[AI0] 抓取10日市場數據 + 板塊表現 + 新聞...")
        market_data = await market_data_client.get_market_overview()

        # 格式化指數數據
        indices_text = ""
        for idx in market_data.get("indices", []):
            change = idx.get("change_pct", 0)
            emoji = "↑" if change > 0 else "↓" if change < 0 else "→"
            indices_text += f"  {idx['name']}({idx['code']}): {idx['price']} {emoji} {change}%\n"

        if not indices_text:
            indices_text = "  實時數據獲取失敗，使用數據庫統計"

        # 格式化 DB 統計
        db_stats = market_data.get("db_stats", {})
        db_stats_text = json.dumps(db_stats, ensure_ascii=False, indent=2, default=str) if db_stats else "無"

        # 格式化市場形態
        regime = market_data.get("regime", {})
        regime_text = _format_regime(regime)
        regime_days = regime.get("metrics", {}).get("days_analyzed", 0)

        # 格式化多日板塊表現
        sector_perf = market_data.get("sector_performance", [])
        sector_text = _format_sector_performance(sector_perf)

        # 格式化新聞
        news = market_data.get("news", [])
        news_text = _format_news(news)

        # === 關鍵詞新聞追蹤 ===
        # 從板塊表現中識別漲幅最大和跌幅最大的行業，搜索相關新聞
        keyword_news = await _search_keyword_news(sector_perf)
        keyword_news_text = _format_keyword_news(keyword_news)

        # 構建歷史摘要
        history_text = ""
        for h in history[-3:]:
            stats = h.backtest_statistics
            history_text += f"  第{h.iteration}輪: 評分={h.composite_score}, 收益={stats.get('totalReturn', 0)}%\n"

        prompt = PROMPT_TEMPLATE.format(
            indices=indices_text,
            db_stats=db_stats_text,
            regime_text=regime_text,
            regime_days=regime_days,
            sector_text=sector_text,
            news_text=news_text,
            keyword_news_text=keyword_news_text,
            history_text=history_text if history_text else "無（首輪）",
            few_shot=get_few_shot("market_news"),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt, json_mode=True)
        logger.info(f"[AI0 行情新聞] {response[:100]}...")
        return response


def _format_regime(regime: dict) -> str:
    """格式化市場形態數據為 prompt 可讀文本。"""
    if not regime or regime.get("regime_type") == "unknown":
        return "數據不足，無法計算市場形態"

    lines = []
    regime_type = regime.get("regime_type", "unknown")
    description = regime.get("description", "")
    lines.append(f"形態類型: {regime_type}")
    lines.append(f"系統計算描述: {description}")
    lines.append("")

    metrics = regime.get("metrics", {})
    if metrics:
        lines.append("形態指標:")
        lines.append(f"  累計漲跌幅: {metrics.get('total_change', 0)}%")
        lines.append(f"  平均絕對漲跌幅: {metrics.get('avg_abs_change', 0)}%")
        lines.append(f"  最大單日漲幅: {metrics.get('max_change', 0)}%")
        lines.append(f"  最大單日跌幅: {metrics.get('min_change', 0)}%")
        lines.append(f"  波動率(標準差): {metrics.get('volatility', 0)}%")
        lines.append(f"  漲跌交替次數: {metrics.get('alternations', 0)}")
        lines.append(f"  交替率: {metrics.get('alternation_ratio', 0)}")
        lines.append(f"  分析天數: {metrics.get('days_analyzed', 0)}")
        lines.append("")

    multi_day = regime.get("multi_day_data", [])
    if multi_day:
        lines.append("每日明細:")
        for d in multi_day:
            date = d.get("date", "")
            close = d.get("close", 0)
            pct = d.get("pct_chg", 0)
            arrow = "↑" if pct > 0 else "↓" if pct < 0 else "→"
            lines.append(f"  {date}: 收盤{close} {arrow} {pct}%")

    return "\n".join(lines)


def _format_sector_performance(sector_perf: list[dict[str, Any]]) -> str:
    """格式化多日板塊表現數據為 prompt 可讀文本。"""
    if not sector_perf:
        return "無板塊表現數據（後端可能不可用）"

    # 按日期分組
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in sector_perf:
        date = str(row.get("date", ""))
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(row)

    lines = []
    for date in sorted(by_date.keys(), reverse=True):
        sectors = by_date[date]
        # 按平均漲跌幅排序
        sectors_sorted = sorted(sectors, key=lambda x: x.get("avgPctChange", 0) or 0, reverse=True)
        lines.append(f"\n=== {date} ===")
        # 顯示前5強勢 + 前5弱勢
        top5 = sectors_sorted[:5]
        bottom5 = sectors_sorted[-5:] if len(sectors_sorted) > 5 else []
        lines.append("  強勢行業:")
        for s in top5:
            avg_pct = s.get("avgPctChange", 0) or 0
            top_code = s.get("topCode", "")
            top_name = s.get("topCodeName", "")
            top_pct = s.get("topPctChange", 0) or 0
            lines.append(
                f"    {s.get('industry', '')}: 平均{avg_pct:+.2f}% "
                f"領漲:{top_name}({top_code}) {top_pct:+.2f}%"
            )
        if bottom5 and len(sectors_sorted) > 5:
            lines.append("  弱勢行業:")
            for s in bottom5:
                avg_pct = s.get("avgPctChange", 0) or 0
                lines.append(f"    {s.get('industry', '')}: 平均{avg_pct:+.2f}%")

    return "\n".join(lines)


def _format_news(news: list[dict[str, Any]]) -> str:
    """格式化新聞列表為 prompt 可讀文本。"""
    if not news:
        return "無新聞數據（新聞抓取失敗）"

    lines = []
    for n in news[:15]:  # 限制前15條避免 token 過多
        title = n.get("title", "")
        source = n.get("source", "")
        date = n.get("date", "")
        lines.append(f"  [{date}] {title} ({source})")

    return "\n".join(lines)


def _format_keyword_news(keyword_news: dict[str, list[dict[str, Any]]]) -> str:
    """格式化關鍵詞新聞為 prompt 可讀文本。"""
    if not keyword_news:
        return "無關鍵詞新聞（搜索失敗或無相關新聞）"

    lines = []
    for keyword, news_list in keyword_news.items():
        lines.append(f"\n=== 關鍵詞「{keyword}」相關新聞 ===")
        if not news_list:
            lines.append("  無相關新聞")
            continue
        for n in news_list[:5]:  # 每個關鍵詞最多5條
            title = n.get("title", "")
            source = n.get("source", "")
            date = n.get("date", "")
            lines.append(f"  [{date}] {title} ({source})")

    return "\n".join(lines)


async def _search_keyword_news(sector_perf: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """從板塊表現中識別漲幅最大和跌幅最大的行業，搜索相關新聞。

    用於利好/利空方向的新聞追蹤，確保分析基於真實新聞而非編造。
    """
    if not sector_perf:
        return {}

    # 計算每個行業的累計漲跌幅
    industry_changes: dict[str, list[float]] = {}
    for row in sector_perf:
        industry = row.get("industry", "")
        avg_pct = row.get("avgPctChange", 0) or 0
        if industry not in industry_changes:
            industry_changes[industry] = []
        industry_changes[industry].append(avg_pct)

    # 計算累計漲跌幅
    industry_cumulative = {
        industry: sum(changes) for industry, changes in industry_changes.items()
    }

    # 取漲幅前3和跌幅前3的行業
    sorted_industries = sorted(industry_cumulative.items(), key=lambda x: x[1], reverse=True)
    top_bullish = [name for name, _ in sorted_industries[:3]]
    top_bearish = [name for name, _ in sorted_industries[-3:]]

    # 搜索關鍵詞新聞（提取行業名稱中的關鍵詞）
    keyword_news: dict[str, list[dict[str, Any]]] = {}
    for industry in top_bullish + top_bearish:
        # 從行業名稱提取關鍵詞（去除分類代碼前綴，如 "C39電子設備製造" → "電子設備製造"）
        keyword = industry
        for i, c in enumerate(industry):
            if c.isalpha() and i < 5:
                keyword = industry[i + 1 :]
                break
        keyword = keyword.strip()
        if not keyword:
            keyword = industry

        try:
            news = await market_data_client.search_news_by_keyword(keyword, page_size=5)
            keyword_news[industry] = news
        except Exception as e:
            logger.warning(f"搜索關鍵詞「{keyword}」新聞失敗: {e}")
            keyword_news[industry] = []

    return keyword_news
