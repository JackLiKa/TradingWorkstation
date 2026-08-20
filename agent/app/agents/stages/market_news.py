"""AI 0: 行情新聞分析 — 抓取實時金融數據 + 按行業總結利好利空。

這是優化循環的第一個 AI 節點（在 AI 1 行情分析之前），
負責獲取當天實時市場數據並按行業分類總結。

輸入: 實時市場數據（指數、板塊）、歷史迭代記錄
輸出: 行業情緒總結（利好行業、利空行業、政策聲明）
範式: 自然語言，包含各行業利好利空分析
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
4. 輸出結構化的行業情緒總結

【數據真實性鐵律】
- 只能引用上方 prompt 中「實時大盤指數」和「數據庫統計」區塊提供的數據
- 禁止編造未在輸入中出現的指數點位、漲跌幅、成交額、行業數據
- 禁止引用訓練記憶中的 A 股歷史行情或個股數據
- 禁止編造政策消息、新聞事件、監管動態——輸入中沒有就不要提
- 如果實時數據獲取失敗，明確標註「實時數據不可用」，不要假裝有數據
- 所有引用的數值必須能在上方輸入中找到對應來源"""

PROMPT_TEMPLATE = """請分析今天的實時金融市場數據，按行業總結利好利空。

## 實時大盤指數
{indices}

## 數據庫統計
{db_stats}

## 歷史優化記錄
{history_text}

{few_shot}

## 你的任務
1. 分析大盤走勢（上漲/下跌/震盪），判斷市場情緒
2. 識別強勢行業（利好）和弱勢行業（利空），每個行業必須引用上方指數區塊中的具體漲跌幅數據
3. 基於數據庫統計推斷可能的資金流向（不要編造未在統計中出現的數據）
4. 總結哪些行業適合選股，哪些應該避開

【數據引用要求】
- 所有引用的指數點位、漲跌幅、成交額必須來自上方「實時大盤指數」區塊
- 所有引用的統計數據必須來自上方「數據庫統計」區塊
- 禁止編造任何未在輸入中出現的數值、行業名稱、政策消息
- 如果某項數據缺失，標註「未提供」而非編造

請按以下格式輸出（自然語言，不要 JSON）：

### 市場情緒
（1-2句話，引用上方指數區塊中的具體漲跌幅描述整體市場情緒）

### 利好行業
（列出 2-3 個強勢行業，每個行業必須包含：行業名稱 + 來自輸入的漲跌幅 + 基於數據的利好原因）

### 利空行業
（列出 1-2 個弱勢行業，每個行業必須包含：行業名稱 + 來自輸入的跌幅 + 基於數據的利空原因）

### 選股建議
（1-2句話，明確指出關注哪些行業的股票，避開哪些）"""


class MarketNewsStage(BaseStage):
    """AI 0: 行情新聞分析節點 — 抓取實時數據 + AI 總結。"""

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

        # === 抓取實時市場數據 ===
        logger.info("[AI0] 抓取實時市場數據...")
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

        # 構建歷史摘要
        history_text = ""
        for h in history[-3:]:
            stats = h.backtest_statistics
            history_text += f"  第{h.iteration}輪: 評分={h.composite_score}, 收益={stats.get('totalReturn', 0)}%\n"

        prompt = PROMPT_TEMPLATE.format(
            indices=indices_text,
            db_stats=db_stats_text,
            history_text=history_text if history_text else "無（首輪）",
            few_shot=get_few_shot("market_news"),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI0 行情新聞] {response[:100]}...")
        return response
