"""AI 4: 提示詞生成 — 根據反思結論，生成下一輪的 prompt 指引。

輸入: 反思結論、回測統計、綜合評分、歷史記錄
輸出: 精準指引文本（2-3 句話）
範式: 自然語言，包含應調整的參數、避免的策略、追求的目標
"""
import logging
from typing import Any

from app.agents.stages.base import BaseStage

logger = logging.getLogger("agent.stage.prompt")

SYSTEM_PROMPT = "你是一個 AI 提示詞工程師，擅長為量化策略優化生成精準的指引提示詞。"

PROMPT_TEMPLATE = """請根據反思結論，為下一輪策略生成生成精準的指引提示詞。

## 回測反思結論
{reflection}

## 當前評分
{composite_score}

## 歷史趨勢
{history_text}

## 你的任務
生成一段簡潔的指引（2-3句話），告訴策略生成 AI 下一輪應該：
1. 重點調整哪些參數
2. 避免什麼樣的策略
3. 追求什麼樣的目標

直接輸出指引，不要 JSON 格式。"""


class PromptGenerationStage(BaseStage):
    """AI 4: 提示詞生成節點。"""

    def __init__(self):
        super().__init__(stage_name="prompt_generation", display_name="AI 4 · 提示詞生成")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行提示詞生成。

        kwargs:
            reflection: str — 回測反思結論
            stats: dict — 回測統計
            composite_score: float — 綜合評分
            history: list[IterationResult] — 歷史記錄
        """
        reflection = kwargs.get("reflection", "")
        stats = kwargs.get("stats", {})
        composite_score = kwargs.get("composite_score", 0)
        history = kwargs.get("history", [])

        # 構建歷史趨勢
        history_text = ""
        for h in history[-3:]:
            s = h.backtest_statistics
            history_text += f"  第{h.iteration}輪: 評分={h.composite_score}, 收益={s.get('totalReturn', 0)}%\n"

        prompt = PROMPT_TEMPLATE.format(
            reflection=reflection,
            composite_score=composite_score,
            history_text=history_text if history_text else "無",
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI4 提示詞生成] {response[:100]}...")
        return response
