"""AI 3: 回測反思 — 分析回測結果，輸出結論和改進方向。

輸入: 回測統計、綜合評分、選股條件、市場環境、歷史記錄
輸出: 結構化分析文本
範式: 自然語言，包含策略優缺點、收益來源、風險控制、改進方向
"""
import json
import logging
from typing import Any

from app.agents.stages.base import BaseStage

logger = logging.getLogger("agent.stage.reflection")

SYSTEM_PROMPT = "你是一個專業的量化策略回測分析師，擅長從回測結果中發現問題並提出改進方向。"

PROMPT_TEMPLATE = """請分析以下回測結果，得出反思結論。

## 回測統計
- 策略總收益: {total_return}%
- 年化收益: {annual_return}%
- 基準收益: {benchmark_return}%
- 超額收益: {excess_return}%
- 最大回撤: {max_drawdown}%
- 夏普比率: {sharpe}
- 調倉次數: {rebalance_count}
- 交易筆數: {total_trades}

## 綜合評分
{composite_score}（收益40% + 回撤控制30% + 夏普30%）

## 當前選股條件
{active_filters}

## 市場環境
{market_context}

## 歷史優化記錄
{history_text}

## 你的任務
分析當前策略的表現，指出：
1. 策略的優點和不足
2. 收益來源（選股還是擇時？）
3. 風險控制效果
4. 具體的改進方向（2-3條）

直接輸出分析結果，不要 JSON 格式。"""


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

        # 構建歷史摘要
        history_text = ""
        for h in history[-5:]:
            s = h.backtest_statistics
            history_text += (
                f"  第{h.iteration}輪: 評分={h.composite_score}, 收益={s.get('totalReturn', 0)}%, "
                f"回撤={s.get('maxDrawdown', 0)}%, 夏普={s.get('sharpe', 0)}\n"
            )

        active_filters = {k: v for k, v in criteria.items() if v is not None and v != False and v != "any" and v != 0}

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
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI3 回測反思] {response[:100]}...")
        return response
