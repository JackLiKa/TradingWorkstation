"""AI 1: 行情分析 — 分析市場環境，輸出市場狀態描述。

輸入: 市場數據（dashboard summary）、歷史迭代記錄、上一輪反思
輸出: 市場趨勢分析文本（2-4 句話）
範式: 自然語言，包含市場趨勢、波動率、適合策略類型
"""

import json
import logging

from app.agents.few_shot import get_few_shot
from app.agents.stages.base import BaseStage

logger = logging.getLogger("agent.stage.market")

SYSTEM_PROMPT = """你是一個專業的 A 股市場分析師，擅長分析市場環境和趨勢。

【數據真實性鐵律】
- 只能引用上方 prompt 中「市場數據」區塊提供的數據
- 禁止編造未在輸入中出現的指數點位、漲跌幅、成交額、市盈率等數值
- 禁止引用訓練記憶中的 A 股歷史行情、個股數據、政策事件
- 禁止編造新聞消息或政策動態
- 所有引用的數值必須能在上方「市場數據」中找到對應來源
- 如果數據不足，標註「數據不足」而非用編造的數據填充"""

PROMPT_TEMPLATE = """請分析當前 A 股市場環境。

## 市場數據
{market_data}

## 歷史優化記錄
{history_text}

## 上一輪反思結論
{prev_reflection}

{few_shot}

## 你的任務
分析當前市場環境（2-3句話），必須包括：
1. 市場整體趨勢（上漲/下跌/震盪），引用上方「市場數據」中的具體數據（如上漲股票佔比、指數漲跌幅），必須包含「趨勢」一詞
2. 波動率水平（高/中/低），引用上方「市場數據」中的具體數值，必須包含「波動」一詞
3. 適合的策略類型（趨勢跟蹤/均值回歸/防禦等），基於上方數據說明理由，必須包含「策略」一詞

【數據引用要求】
- 所有引用的數值必須來自上方「市場數據」區塊
- 禁止編造未在輸入中出現的數據
- 禁止引用訓練記憶中的 A 股歷史行情
- 如果某項數據缺失，不要假設它的值

直接輸出分析結果，不要 JSON 格式。控制在 100-200 字。"""


class MarketAnalysisStage(BaseStage):
    """AI 1: 行情分析節點。"""

    def __init__(self):
        super().__init__(stage_name="market_analysis", display_name="AI 1 · 行情分析")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行情情分析。

        kwargs:
            market_data: dict — dashboard summary 數據
            history: list[IterationResult] — 歷史迭代記錄
            prev_reflection: str — 上一輪反思結論
        """
        market_data = kwargs.get("market_data", {})
        history = kwargs.get("history", [])
        prev_reflection = kwargs.get("prev_reflection", "")

        # 構建歷史摘要
        history_text = ""
        for h in history[-3:]:
            stats = h.backtest_statistics
            history_text += (
                f"  第{h.iteration}輪: 收益={stats.get('totalReturn', 0)}%, "
                f"回撤={stats.get('maxDrawdown', 0)}%, 夏普={stats.get('sharpe', 0)}, "
                f"評分={h.composite_score}\n"
            )

        prompt = PROMPT_TEMPLATE.format(
            market_data=json.dumps(market_data, ensure_ascii=False, indent=2, default=str),
            history_text=history_text if history_text else "無（首輪）",
            prev_reflection=prev_reflection if prev_reflection else "無（首輪）",
            few_shot=get_few_shot("market_analysis"),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI1 行情分析] {response[:100]}...")
        return response
