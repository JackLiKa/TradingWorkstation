"""AI 4: 提示詞生成 — 根據反思結論，生成下一輪的 prompt 指引。

輸入: 反思結論、回測統計、綜合評分、歷史記錄
輸出: 精準指引文本（2-3 句話）
範式: 自然語言，包含應調整的參數、避免的策略、追求的目標
"""

import logging

from app.agents.few_shot import get_few_shot
from app.agents.stages.base import BaseStage

logger = logging.getLogger("agent.stage.prompt")

SYSTEM_PROMPT = """你是一個 AI 提示詞工程師，擅長為量化策略優化生成精準的指引提示詞。

【數據真實性鐵律】
- 指引內容必須基於上方「回測反思結論」和「歷史趨勢」中的具體內容
- 禁止編造未在輸入中出現的評分、收益、回撤等數據
- 禁止引用訓練記憶中的 A 股歷史行情或個股數據
- 調整建議必須針對上方反思結論中提到的具體問題
- 量化目標必須基於上方「當前評分」和「歷史趨勢」中的數據，不要編造目標"""

PROMPT_TEMPLATE = """請根據反思結論，為下一輪策略生成生成精準的指引提示詞。

## 回測反思結論
{reflection}

## 當前評分
{composite_score}

## 歷史趨勢
{history_text}

{few_shot}

## 你的任務
生成一段簡潔的指引（2-3句話），告訴策略生成 AI 下一輪應該：
1. 重點調整哪些參數（必須用具體參數名，如 minTurn、stopLossPct、minVolumeRatio，且必須針對上方反思結論提到的問題，必須包含「調整」一詞）
2. 避免什麼樣的策略（基於上方反思結論或歷史趨勢中的具體教訓，必須包含「避免」一詞）
3. 追求什麼樣的目標（量化目標，基於上方「當前評分」和「歷史趨勢」中的數據，必須包含「目標」一詞）

【數據引用要求】
- 調整建議必須針對上方「回測反思結論」中提到的具體問題
- 量化目標必須基於上方「當前評分」和「歷史趨勢」中的數據
- 禁止編造未在輸入中出現的數據
- 禁止引用訓練記憶中的 A 股歷史行情

直接輸出指引，不要 JSON 格式。控制在 80-150 字。"""


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
        kwargs.get("stats", {})
        composite_score = kwargs.get("composite_score", 0)
        history = kwargs.get("history", [])

        # 構建歷史趨勢（最近 5 輪，冷啟動時由種子上下文補充）
        history_text = ""
        for h in history[-5:]:
            s = h.backtest_statistics
            history_text += f"  第{h.iteration}輪: 評分={h.composite_score}, 收益={s.get('totalReturn', 0)}%\n"

        prompt = PROMPT_TEMPLATE.format(
            reflection=reflection,
            composite_score=composite_score,
            history_text=history_text if history_text else "無",
            few_shot=get_few_shot("prompt_generation"),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI4 提示詞生成] {response[:100]}...")
        return response
