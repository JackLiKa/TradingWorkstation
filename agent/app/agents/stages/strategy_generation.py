"""AI 2: 策略生成 — 根據市場狀態 + 歷史策略，生成選股條件。

輸入: 市場分析、當前選股條件、回測配置、歷史記錄、上一輪反思、下一輪提示詞
輸出: JSON { reasoning, criteria }
範式: 必須是有效 JSON，包含 reasoning 和 criteria 字段
"""
import json
import logging
from typing import Any

from app.agents.stages.base import BaseStage

logger = logging.getLogger("agent.stage.strategy")

SYSTEM_PROMPT = "你是一個專業的量化策略設計師，擅長 A 股選股策略設計和參數調優。"

PROMPT_TEMPLATE = """你是一個量化策略設計師。請根據市場分析結果生成選股條件。

## 市場分析
{market_context}

## 上一輪反思結論
{prev_reflection}

## 下一輪提示詞指引
{next_prompt}

## 當前選股條件
{current_criteria}

## 回測配置（不可修改）
{config}

## 歷史優化記錄
{history_text}

## 你的任務
1. 根據市場分析和反思結論，調整選股條件
2. 每次只調整 1-3 個參數，不要大幅變動
3. 說明你的調整理由

請嚴格按以下 JSON 格式返回:
```json
{{
  "reasoning": "調整理由（1-2句話）",
  "criteria": {{
    "asOfDate": "{asof_date}",
    "adjustflag": {adjustflag},
    "excludeSt": true,
    "maxResults": 50,
    "sortBy": "score",
    "minClose": null,
    "maxClose": null,
    "minPctChange": null,
    "maxPctChange": null,
    "minTurn": null,
    "maxTurn": null,
    "minAmplitude": null,
    "maxAmplitude": null,
    "minVolume": null,
    "minAmount": null,
    "minVolumeRatio": null,
    "maxVolumeRatio": null,
    "minReturn20": null,
    "maxReturn20": null,
    "minReturn60": null,
    "maxReturn60": null,
    "minReturn120": null,
    "maxReturn120": null,
    "minRsi14": null,
    "maxRsi14": null,
    "minKValue": null,
    "maxKValue": null,
    "minJValue": null,
    "maxJValue": null,
    "minMacdHist": null,
    "maxMacdHist": null,
    "macdCrossSignal": "any",
    "macdCrossWithinDays": 0,
    "kdjCrossSignal": "any",
    "kdjCrossWithinDays": 0,
    "bollPosition": "any",
    "priceAboveMa5": false,
    "priceAboveMa20": false,
    "priceAboveMa60": false,
    "ma5AboveMa20": false,
    "ma20AboveMa60": false
  }}
}}
```

注意:
- 數值參數用數字或 null，不要用字符串
- 信號字段用 "any"/"golden_cross"/"death_cross"/"none"
- 布爾字段用 true/false
- 只調整選股條件，不要改變回測配置"""


class StrategyGenerationStage(BaseStage):
    """AI 2: 策略生成節點。"""

    def __init__(self):
        super().__init__(stage_name="strategy_generation", display_name="AI 2 · 策略生成")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行策略生成。

        kwargs:
            market_context: str — 市場分析結果
            current_criteria: dict — 當前選股條件
            config: dict — 回測配置
            history: list[IterationResult] — 歷史記錄
            prev_reflection: str — 上一輪反思
            next_prompt: str — 下一輪提示詞指引
        """
        market_context = kwargs.get("market_context", "")
        current_criteria = kwargs.get("current_criteria", {})
        config = kwargs.get("config", {})
        history = kwargs.get("history", [])
        prev_reflection = kwargs.get("prev_reflection", "")
        next_prompt = kwargs.get("next_prompt", "")

        # 構建歷史摘要
        history_text = ""
        for h in history[-5:]:
            stats = h.backtest_statistics
            active_filters = {k: v for k, v in h.criteria.items() if v is not None and v != False and v != "any" and v != 0}
            history_text += (
                f"  第{h.iteration}輪: 評分={h.composite_score}, 收益={stats.get('totalReturn', 0)}%, "
                f"回撤={stats.get('maxDrawdown', 0)}%, 夏普={stats.get('sharpe', 0)}, "
                f"條件={json.dumps(active_filters, ensure_ascii=False)}\n"
            )

        from datetime import datetime
        asof_date = current_criteria.get("asOfDate", datetime.now().strftime("%Y-%m-%d"))
        adjustflag = current_criteria.get("adjustflag", 3)

        prompt = PROMPT_TEMPLATE.format(
            market_context=market_context,
            prev_reflection=prev_reflection if prev_reflection else "無",
            next_prompt=next_prompt if next_prompt else "無（按你的判斷生成）",
            current_criteria=json.dumps(current_criteria, ensure_ascii=False, indent=2),
            config=json.dumps(config, ensure_ascii=False, indent=2),
            history_text=history_text if history_text else "無（首輪）",
            asof_date=asof_date,
            adjustflag=adjustflag,
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI2 策略生成] {response[:100]}...")
        return response


def parse_strategy_output(response: str) -> dict[str, Any]:
    """解析策略生成 AI 的 JSON 輸出。"""
    json_start = response.find("```json")
    if json_start >= 0:
        json_start = response.find("{", json_start)
        json_end = response.rfind("}")
        if json_start >= 0 and json_end > json_start:
            return json.loads(response[json_start:json_end + 1])

    brace_start = response.find("{")
    brace_end = response.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        return json.loads(response[brace_start:brace_end + 1])

    raise ValueError(f"無法從 LLM 響應中提取 JSON: {response[:200]}")
