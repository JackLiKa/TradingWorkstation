"""AI 3: 回測反思 — 分析回測結果，輸出結論和改進方向。

輸入: 回測統計、綜合評分、選股條件、市場環境、歷史記錄
輸出: 結構化分析文本
範式: 自然語言，包含策略優缺點、收益來源、風險控制、改進方向
"""

import json
import logging

from app.agents.few_shot import get_few_shot
from app.agents.stages.base import BaseStage

logger = logging.getLogger("agent.stage.reflection")

SYSTEM_PROMPT = """你是一個專業的量化策略回測分析師，擅長從回測結果中發現問題並提出改進方向。

【數據真實性鐵律】
- 只能引用上方 prompt 中「回測統計」「當前選股條件」「歷史記錄」區塊提供的數據
- 禁止編造未在輸入中出現的回測指標、收益數據、交易筆數
- 禁止引用訓練記憶中的 A 股歷史行情或個股表現來評價策略
- 禁止編造市場事件或政策來解釋回測結果
- 所有引用的數值（收益、回撤、夏普等）必須來自上方「回測統計」區塊
- 改進方向必須基於上方數據的具體問題，不要給出無數據支撐的泛泛建議"""

PROMPT_TEMPLATE = """請分析以下回測結果，得出反思結論（控制在 500 字以內）。

## 回測統計
- 總收益: {total_return}% | 年化: {annual_return}% | 基準: {benchmark_return}% | 超額: {excess_return}%
- 最大回撤: {max_drawdown}% | 夏普: {sharpe} | 調倉: {rebalance_count}次 | 交易: {total_trades}筆
- 綜合評分: {composite_score}

## 當前選股條件
{active_filters}

## 市場環境
{market_context}

## 歷史記錄（最近3輪）
{history_text}

{few_shot}

## 輸出要求（簡潔，500字以內，必須引用上方具體數值）
1. 優點和不足（各1-2句，引用上方「回測統計」中的收益/回撤/夏普等具體數值）
2. 收益來源（選股/擇時，1句，基於上方「當前選股條件」和「回測統計」說明依據）
3. 風險控制評價（1句，引用上方「回測統計」中的回撤數據）
4. 改進方向（2-3條，每條必須包含：具體參數名 + 調整方向 + 基於上方數據的預期效果）

【數據引用要求】
- 所有引用的收益、回撤、夏普、交易筆數必須來自上方「回測統計」區塊
- 改進方向必須針對上方「回測統計」或「當前選股條件」中暴露的具體問題
- 禁止編造未在輸入中出現的數據或市場事件來解釋回測結果
- 禁止引用訓練記憶中的 A 股歷史行情

直接輸出分析，不要 JSON。"""


class BacktestReflectionStage(BaseStage):
    """AI 3: 回測反思節點。"""

    def __init__(self):
        super().__init__(stage_name="backtest_reflection", display_name="AI 3 · 回測反思")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行回測反思。

        kwargs:
            stats: dict — 回測統計
            composite_score: float — 綜合評分
            criteria: dict — 選股條件
            market_context: str — 市場環境
            history: list[IterationResult] — 歷史記錄
        """
        stats = kwargs.get("stats", {})
        composite_score = kwargs.get("composite_score", 0)
        criteria = kwargs.get("criteria", {})
        market_context = kwargs.get("market_context", "")
        history = kwargs.get("history", [])

        # 構建歷史摘要（只取最近 3 輪，避免 prompt 過長導致 LLM 思考太久）
        history_text = ""
        for h in history[-3:]:
            s = h.backtest_statistics
            history_text += (
                f"  第{h.iteration}輪: 評分={h.composite_score}, 收益={s.get('totalReturn', 0)}%, "
                f"回撤={s.get('maxDrawdown', 0)}%, 夏普={s.get('sharpe', 0)}\n"
            )

        active_filters = {
            k: v for k, v in criteria.items() if v is not None and v is not False and v != "any" and v != 0
        }
        # 截斷市場環境文本，避免 prompt 過長
        if len(market_context) > 500:
            market_context = market_context[:500] + "..."

        prompt = PROMPT_TEMPLATE.format(
            total_return=stats.get("totalReturn", 0),
            annual_return=stats.get("annualReturn", 0),
            benchmark_return=stats.get("benchmarkReturn", 0),
            excess_return=stats.get("excessReturn", 0),
            max_drawdown=stats.get("maxDrawdown", 0),
            sharpe=stats.get("sharpe", 0),
            rebalance_count=stats.get("rebalanceCount", 0),
            total_trades=stats.get("totalTrades", 0),
            composite_score=composite_score,
            active_filters=json.dumps(active_filters, ensure_ascii=False, indent=2),
            market_context=market_context,
            history_text=history_text if history_text else "無",
            few_shot=get_few_shot("backtest_reflection"),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI3 回測反思] {response[:100]}...")
        return response
