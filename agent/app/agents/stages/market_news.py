"""AI 0: 行情新聞分析 — 抓取實時金融數據 + 按行業總結利好利空 + 市場形態識別。

這是優化循環的第一個 AI 節點（在 AI 1 行情分析之前），
負責獲取當天實時市場數據並按行業分類總結，同時識別多日市場形態。

輸入: 實時市場數據（指數、板塊）、多日指數歷史、歷史迭代記錄
輸出: 行業情緒總結（市場形態、利好行業、利空行業、選股建議）
範式: 自然語言，包含市場形態識別和各行業利好利空分析
"""

import json
import logging

from app.agents.few_shot import get_few_shot
from app.agents.stages.base import BaseStage
from app.services.market_data_client import market_data_client

logger = logging.getLogger("agent.stage.market_news")

SYSTEM_PROMPT = """你是一個專業的 A 股市場新聞分析師，擅長從實時行情數據中提取行業利好利空信息。
你需要：
1. 分析大盤指數走勢，判斷市場整體情緒
2. 分析各行業板塊的漲跌情況，識別強勢和弱勢行業
3. 結合數據庫統計，推斷可能的資金流向
4. **識別市場形態**：基於多日歷史數據，判斷當前處於哪種市場形態
5. 輸出結構化的行業情緒總結

【市場形態類型】
|- 震盪行情：漲跌交替頻繁，幅度有限，無明確方向
|- 上漲中繼：上漲後小幅回調，可能繼續上漲
|- 下跌中繼：下跌後小幅反彈，可能繼續下跌
|- 上漲趨勢：連續上漲，回撤小
|- 下跌趨勢：連續下跌，反彈小

【為什麼要識別形態】
|- 單看一天的漲跌不夠：藍籌承壓+成長上攻可能是輪動，也可能是震盪
|- 連續多日交替漲跌 → 可能是震盪行情，適合均值回歸策略
|- 連續上漲後回調 → 可能是上漲中繼，適合趨勢跟蹤策略
|- 連續下跌後反彈 → 可能是下跌中繼，應防禦為主

【數據真實性鐵律】
|- 只能引用上方 prompt 中「實時大盤指數」「數據庫統計」「多日市場形態」區塊提供的數據
|- 禁止編造未在輸入中出現的指數點位、漲跌幅、成交額、行業數據
|- 禁止引用訓練記憶中的 A 股歷史行情或個股數據
|- 禁止編造政策消息、新聞事件、監管動態——輸入中沒有就不要提
|- 如果實時數據獲取失敗，明確標註「實時數據不可用」，不要假裝有數據
|- 所有引用的數值必須能在上方輸入中找到對應來源"""

PROMPT_TEMPLATE = """請分析今天的實時金融市場數據，按行業總結利好利空，並識別市場形態。

## 實時大盤指數
{indices}

## 數據庫統計
{db_stats}

## 多日市場形態（最近{regime_days}日）
{regime_text}

## 歷史優化記錄
{history_text}

{few_shot}

## 你的任務
1. **識別市場形態**：基於上方「多日市場形態」區塊，判斷當前處於哪種形態（震盪/上漲中繼/下跌中繼/上漲趨勢/下跌趨勢），引用多日數據中的具體漲跌幅和交替次數
2. 分析大盤走勢（上漲/下跌/震盪），判斷市場情緒
3. 識別強勢行業（利好）和弱勢行業（利空），每個行業必須引用上方指數區塊中的具體漲跌幅數據
4. 基於數據庫統計推斷可能的資金流向（不要編造未在統計中出現的數據）
5. 總結哪些行業適合選股，哪些應該避開

【數據引用要求】
|- 所有引用的指數點位、漲跌幅、成交額必須來自上方「實時大盤指數」區塊
|- 所有引用的統計數據必須來自上方「數據庫統計」區塊
|- 形態判斷必須基於上方「多日市場形態」區塊的數據
|- 禁止編造任何未在輸入中出現的數值、行業名稱、政策消息
|- 如果某項數據缺失，標註「未提供」而非編造

請按以下格式輸出（自然語言，不要 JSON）：

### 市場形態
（1-2句話，引用上方「多日市場形態」中的具體數據，判斷當前處於哪種形態：震盪/上漲中繼/下跌中繼/上漲趨勢/下跌趨勢，必須包含形態類型名稱）

### 市場情緒
（1-2句話，引用上方指數區塊中的具體漲跌幅描述整體市場情緒，必須包含「市場情緒」一詞）

### 利好行業
（列出 2-3 個強勢行業，每個行業必須包含：行業名稱 + 來自輸入的漲跌幅 + 基於數據的利好原因，必須包含「利好」一詞）

### 利空行業
（列出 1-2 個弱勢行業，每個行業必須包含：行業名稱 + 來自輸入的跌幅 + 基於數據的利空原因，必須包含「利空」一詞）

### 選股建議
（1-2句話，明確指出選股時關注哪些行業的股票，避開哪些，必須包含「選股」一詞）"""


class MarketNewsStage(BaseStage):
    """AI 0: 行情新聞分析節點 — 抓取實時數據 + 市場形態識別 + AI 總結。"""

    def __init__(self):
        super().__init__(stage_name="market_news", display_name="AI 0 · 行情新聞")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行情情新聞分析。

        kwargs:
            history: list[IterationResult] — 歷史迭代記錄
        """
        history = kwargs.get("history", [])

        # === 抓取實時市場數據（含多日形態）===
        logger.info("[AI0] 抓取實時市場數據 + 多日形態...")
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
            history_text=history_text if history_text else "無（首輪）",
            few_shot=get_few_shot("market_news"),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
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
