"""回顧分析 AI — 每5輪分析各AI節點的輸入輸出，發現問題、提出優化總結和改善方案。

這是一個「元認知」節點，不參與單輪優化循環，而是在每5輪結束後回顧分析：
1. 收集最近5輪各AI階段的輸入輸出摘要
2. 分析評分趨勢、各階段質量、重複問題
3. 產出具體的優化總結和改善方案
4. 將結果注入下一輪的 next_prompt，指導AI改進

觸發方式：
- 自動：optimizer 每完成 RETROSPECTIVE_INTERVAL 輪後觸發
- 手動：API 端點 /api/agent/retrospective/trigger

輸出：結構化 JSON（findings + optimization_summary + improvement_plan + stage_issues + score_trend + recommendations）
持久化：結果保存到 state.last_retrospective + DB agent_state 表
"""

import json
import logging
from datetime import datetime
from typing import Any

from app.agents.few_shot import get_few_shot
from app.agents.state import OptimizerState, RetrospectiveResult, RETROSPECTIVE_INTERVAL
from app.agents.stages.base import BaseStage

logger = logging.getLogger("agent.stage.retrospective")

SYSTEM_PROMPT = """你是一個專業的量化策略優化回顧分析師，擅長從多輪AI優化迭代中發現問題、總結規律、提出具體改善方案。

你的職責：
1. **問題發現**：分析最近5輪各AI節點的輸入輸出，識別重複出現的問題模式
2. **質量評估**：評估各AI階段的輸出質量趨勢（是否改善/退化/停滯）
3. **優化總結**：總結5輪優化的整體表現、關鍵轉折點、核心瓶頸
4. **改善方案**：提出具體可執行的改善措施（不是籠統建議）
5. **趨勢分析**：分析評分趨勢，預測下一個5輪窗口的改進方向

【分析原則】
|- 基於具體數據：引用具體輪次的具體問題，不要泛泛而談
|- 問題導向：聚焦「為什麼效果不好」而非「效果好不好」
|- 可執行性：改善方案必須是AI能在下一輪執行的具體指令
|- 不越權：只提出建議，不直接修改策略邏輯或風控規則
|- 數據真實：只引用上方輸入中提供的數據，禁止編造

【常見問題模式】
|- 策略生成疊加條件：AI2傾向新增條件而非替換，導致過度收斂
|- 新聞引用不足：AI0未引用具體新聞標題驗證利好利空
|- 反思籠統：AI3建議缺乏具體參數值
|- 行業集中：連續多輪聚焦同一行業，分散度不足
|- 評分停滯：連續多輪評分變化<1分，陷入局部最優
|- 0交易：條件過嚴導致策略無法產生交易

【規則覆核（每次輸出前必須執行）】
生成最終輸出前，silently 覆核：①數據真實性（引用值是否都在輸入中）②JSON 格式（合法 JSON、無 markdown 標記）③合規（不推薦個股買賣）④職責邊界（只提建議不修改策略）⑤數據不足標註（不編造）⑥禁止事項（無廢話、不重複輸入）。任一不滿足則修正後再輸出。"""

PROMPT_TEMPLATE = """請回顧分析最近{window_size}輪優化迭代的各AI節點表現。

## 回顧範圍
第 {start_iter}-{end_iter} 輪

## 評分趨勢
{score_trend}

## 各輪各階段摘要
{iterations_detail}

## 上一輪回顧分析結論（如有）
{prev_retrospective}

{few_shot}

## 你的任務
1. **問題發現**：分析各AI節點在5輪中的表現，識別重複出現的問題模式（如策略生成疊加條件、新聞引用不足、反思籠統等）
2. **優化總結**：總結5輪優化的整體趨勢、關鍵轉折點、核心瓶頸
3. **改善方案**：提出3-5條具體可執行的改善措施，每條必須是AI能在下一輪執行的具體指令
4. **各階段問題**：按階段列出具體問題（market_news/strategy_generation/backtest_reflection等）
5. **評分趨勢分析**：分析評分變化趨勢，預測改進方向
6. **具體建議列表**：列出可在下一輪執行的具體建議

【輸出要求】
|- findings 必須引用具體輪次的具體問題（如「第3輪AI2疊加maxRsi14導致0交易」）
|- improvement_plan 必須是具體可執行的指令（如「AI2下次調整時替換而非疊加條件」）
|- recommendations 每條必須是AI能在下一輪執行的具體動作
|- 禁止籠統建議（如「需要改進」無具體措施）
|- 禁止編造未在輸入中出現的數據或輪次

請嚴格按以下 JSON 格式返回（不要加 markdown 代碼塊標記）:
{{
  "findings": "發現的問題（引用具體輪次和具體問題）",
  "optimization_summary": "5輪優化的整體總結",
  "improvement_plan": "具體可執行的改善方案（3-5條）",
  "stage_issues": {{
    "market_news": "該階段的具體問題",
    "strategy_generation": "該階段的具體問題",
    "backtest_reflection": "該階段的具體問題"
  }},
  "score_trend": "評分趨勢分析",
  "recommendations": ["具體建議1", "具體建議2", "具體建議3"]
}}

注意:
|- JSON 中不要加 ```json 標記
|- findings 和 improvement_plan 用 \\n 分行
|- recommendations 是字符串數組，每條一個具體建議
|- stage_issues 只列出有問題的階段，無問題的階段可省略"""


class RetrospectiveStage(BaseStage):
    """回顧分析 AI — 每5輪分析各AI輸入輸出的元認知節點。"""

    def __init__(self):
        super().__init__(stage_name="retrospective", display_name="回顧分析")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行回顧分析。

        kwargs:
            iterations: list[IterationResult] — 最近5輪的迭代結果
            prev_retrospective: str — 上一輪回顧分析結論（可選）
        """
        iterations: list = kwargs.get("iterations", [])
        prev_retrospective: str = kwargs.get("prev_retrospective", "")

        if not iterations:
            return json.dumps({
                "findings": "無迭代數據可分析",
                "optimization_summary": "無",
                "improvement_plan": "無",
                "stage_issues": {},
                "score_trend": "無",
                "recommendations": [],
            }, ensure_ascii=False)

        start_iter = iterations[0].iteration
        end_iter = iterations[-1].iteration
        window_size = len(iterations)

        # 構建評分趨勢
        scores = [it.composite_score for it in iterations]
        score_trend = " → ".join([f"第{it.iteration}輪:{it.composite_score}" for it in iterations])
        if len(scores) >= 2:
            delta = scores[-1] - scores[0]
            score_trend += f"（總變化: {'+' if delta >= 0 else ''}{delta:.1f}分）"

        # 構建各輪各階段摘要（控制 token 量，每輪只取關鍵信息）
        iterations_detail = _build_iterations_detail(iterations)

        prompt = PROMPT_TEMPLATE.format(
            window_size=window_size,
            start_iter=start_iter,
            end_iter=end_iter,
            score_trend=score_trend,
            iterations_detail=iterations_detail,
            prev_retrospective=prev_retrospective if prev_retrospective else "無（首次回顧）",
            few_shot=get_few_shot("retrospective"),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt, json_mode=True)
        logger.info(f"[回顧分析] {response[:100]}...")
        return response


def _build_iterations_detail(iterations: list) -> str:
    """構建各輪各階段摘要文本（控制 token 量）。

    每輪只提取關鍵信息：
    - 評分、收益、回撤、交易筆數
    - 各階段輸出的前200字符
    - 評委分數
    """
    lines = []
    for it in iterations:
        stats = it.backtest_statistics
        lines.append(f"### 第{it.iteration}輪（評分={it.composite_score}）")
        lines.append(f"- 回測: 收益={stats.get('totalReturn', 0)}%, 回撤={stats.get('maxDrawdown', 0)}%, "
                      f"夏普={stats.get('sharpe', 0)}, 交易={stats.get('totalTrades', 0)}筆")

        # 各階段摘要
        for sr in it.stage_results:
            stage = sr.get("stage_name", "")
            output = sr.get("output", "")
            judge_score = sr.get("judge_score", 0)
            # 截斷輸出避免 token 爆炸
            output_preview = output[:200] if output else ""
            lines.append(f"- {stage}（評委={judge_score}）: {output_preview}")

        # 策略條件摘要
        active_filters = {
            k: v for k, v in it.criteria.items()
            if v is not None and v is not False and v != "any" and v != 0
        }
        if active_filters:
            lines.append(f"- 策略條件: {json.dumps(active_filters, ensure_ascii=False)}")

        # 錯誤信息
        if it.error:
            lines.append(f"- ⚠️錯誤: {it.error[:100]}")
        lines.append("")

    return "\n".join(lines)


def parse_retrospective_output(output: str) -> RetrospectiveResult:
    """解析回顧分析AI的JSON輸出為 RetrospectiveResult。

    Raises:
        ValueError: JSON 解析失敗或缺少必要字段
    """
    cleaned = output.strip()
    # 移除 markdown 代碼塊標記
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"回顧分析 JSON 解析失敗: {e}")

    # 提取 iteration_range 從輸出中無法得知，由調用方設置
    return RetrospectiveResult(
        iteration_range=(0, 0),  # 由調用方覆蓋
        timestamp=datetime.now().isoformat(),
        findings=data.get("findings", ""),
        optimization_summary=data.get("optimization_summary", ""),
        improvement_plan=data.get("improvement_plan", ""),
        stage_issues=data.get("stage_issues", {}),
        score_trend=data.get("score_trend", ""),
        recommendations=data.get("recommendations", []),
    )


async def run_retrospective(
    state: OptimizerState,
    window_size: int = RETROSPECTIVE_INTERVAL,
) -> RetrospectiveResult | None:
    """執行一次回顧分析（自動或手動觸發）。

    Args:
        state: 優化器全局狀態
        window_size: 回顧窗口大小（默認5輪）

    Returns:
        RetrospectiveResult | None: 分析結果，失敗時返回 None
    """
    if len(state.iterations) < window_size:
        logger.info(f"迭代數不足 {window_size} 輪，跳過回顧分析")
        return None

    # 取最近 window_size 輪
    recent_iterations = state.iterations[-window_size:]
    start_iter = recent_iterations[0].iteration
    end_iter = recent_iterations[-1].iteration

    stage = RetrospectiveStage()
    prev_retro_text = ""
    if state.last_retrospective:
        prev_retro_text = state.last_retrospective.to_prompt_text()

    try:
        output = await stage.execute(
            iterations=recent_iterations,
            prev_retrospective=prev_retro_text,
        )
        result = parse_retrospective_output(output)
        result.iteration_range = (start_iter, end_iter)
        result.timestamp = datetime.now().isoformat()

        # 保存到狀態
        state.last_retrospective = result
        state.retrospective_count += 1

        # 將回顧結論注入下一輪 next_prompt
        retro_text = result.to_prompt_text()
        if state.current_next_prompt:
            state.current_next_prompt = f"{state.current_next_prompt}\n\n{retro_text}"
        else:
            state.current_next_prompt = retro_text

        logger.info(
            f"回顧分析完成（第{start_iter}-{end_iter}輪）: "
            f"findings={result.findings[:100]}..."
        )
        return result
    except Exception as e:
        logger.error(f"回顧分析失敗: {e}", exc_info=True)
        return None
