"""AI 0: 行情新聞分析 — 抓取實時金融數據 + 按行業總結利好利空。

這是優化循環的第一個 AI 節點（在 AI 1 行情分析之前），
負責獲取當天實時市場數據並按行業分類總結。

輸入: 實時市場數據（指數、板塊）、歷史迭代記錄
輸出: 行業情緒總結（利好行業、利空行業、政策聲明）
範式: 自然語言，包含各行業利好利空分析
"""
import json
import logging
from typing import Any

from app.agents.stages.base import BaseStage
from app.services.market_data_client import market_data_client

logger = logging.getLogger("agent.stage.market_news")

SYSTEM_PROMPT = """你是一個專業的 A 股市場新聞分析師，擅長從實時行情數據中提取行業利好利空信息。
你需要：
1. 分析大盤指數走勢，判斷市場整體情緒
2. 分析各行業板塊的漲跌情況，識別強勢和弱勢行業
3. 結合數據庫統計，推斷可能的政策影響和資金流向
4. 輸出結構化的行業情緒總結"""

PROMPT_TEMPLATE = """請分析今天的實時金融市場數據，按行業總結利好利空。

## 實時大盤指數
{indices}

## 數據庫統計
{db_stats}

## 歷史優化記錄
{history_text}

## 你的任務
1. 分析大盤走勢（上漲/下跌/震盪），判斷市場情緒
2. 識別強勢行業（利好）和弱勢行業（利空）
3. 推斷可能的資金流向和政策影響
4. 總結哪些行業適合選股，哪些應該避開

請按以下格式輸出（自然語言，不要 JSON）：

### 市場情緒
（1-2句話描述整體市場情緒）

### 利好行業
（列出 2-3 個強勢行業及原因）

### 利空行業
（列出 1-2 個弱勢行業及原因）

### 選股建議
（1-2句話，建議關注哪些行業的股票）"""


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
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI0 行情新聞] {response[:100]}...")
        return response
