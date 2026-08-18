"""AI 節點基類 — AOP 鉤子 + 可觀測性 + 評委集成。

AOP 鉤子:
- pre_execute: 執行前（更新狀態、日誌）
- execute: 實際 AI 調用（子類實現）
- post_execute: 執行後（記錄耗時、更新狀態）
- on_error: 異常處理

可觀測性:
- 記錄每個階段的開始/結束時間、耗時、嘗試次數、評委結果
- 通過 stage_name 和 status 追蹤節點狀態
"""
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.agents.state import StageResult
from app.agents.monitor import node_monitor
from app.core.llm_client import llm_client

logger = logging.getLogger("agent.stage")


class BaseStage(ABC):
    """AI 節點基類 — 子類實現 build_prompt 和 execute。"""

    def __init__(self, stage_name: str, display_name: str):
        self.stage_name = stage_name
        self.display_name = display_name

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """執行 AI 調用，返回原始輸出。子類實現。"""
        ...

    def get_system_prompt(self) -> str:
        """返回該階段的 system prompt（子類可覆蓋）。"""
        return "你是一個專業的 AI 助手。"

    async def run(self, state, judge=None, max_attempts: int = 2, **kwargs) -> StageResult:
        """執行完整流程：pre → execute → judge → post。

        AOP 鉤子：
        - pre_execute: 更新狀態為 running
        - execute: 調用 AI
        - judge: 評委評分（如果有）
        - post_execute: 記錄結果
        - 如果評委不通過且未達最大嘗試次數，重試
        """
        start_time = time.time()
        attempts = 0
        last_output = ""
        last_error = None
        judge_score = 0.0
        judge_passed = True
        judge_feedback = ""

        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            # === pre_execute 鉤子 ===
            state.current_stage = self.stage_name
            state.current_stage_status = "running"
            if attempt == 1:
                node_monitor.record_start(self.stage_name, node_type="ai")
            logger.info(f"[{self.stage_name}] 第 {attempt} 次嘗試")

            try:
                # === execute ===
                last_output = await self.execute(**kwargs)
                last_error = None

                # === judge 鉤子 ===
                if judge:
                    state.current_stage_status = "judging"
                    node_monitor.record_judge(self.stage_name)
                    judge_score, judge_passed, judge_feedback = await judge.evaluate(
                        stage_name=self.stage_name,
                        output=last_output,
                        context=kwargs,
                    )
                    logger.info(
                        f"[{self.stage_name}] 評委: score={judge_score}, passed={judge_passed}, "
                        f"feedback={judge_feedback[:80]}"
                    )

                    if judge_passed:
                        state.current_stage_status = "passed"
                        break
                    else:
                        state.current_stage_status = "retrying"
                        if attempt < max_attempts:
                            logger.info(f"[{self.stage_name}] 評委未通過，重試...")
                            continue
                        else:
                            logger.warning(f"[{self.stage_name}] 評委未通過，已達最大嘗試次數，放行")
                            state.current_stage_status = "passed_with_warning"
                            break
                else:
                    state.current_stage_status = "passed"
                    break

            except Exception as e:
                last_error = str(e)
                state.current_stage_status = "failed"
                logger.error(f"[{self.stage_name}] 執行異常: {e}", exc_info=True)
                if attempt < max_attempts:
                    logger.info(f"[{self.stage_name}] 異常重試...")
                    continue
                break

        duration_ms = int((time.time() - start_time) * 1000)

        # === post_execute 鉤子 ===
        node_monitor.record_end(
            node_id=self.stage_name,
            node_type="ai",
            duration_ms=duration_ms,
            attempts=attempts,
            judge_score=judge_score,
            judge_passed=judge_passed,
            error=last_error,
        )
        result = StageResult(
            stage_name=self.stage_name,
            output=last_output,
            judge_score=judge_score,
            judge_passed=judge_passed,
            judge_feedback=judge_feedback,
            attempts=attempts,
            duration_ms=duration_ms,
            error=last_error,
        )
        logger.info(f"[{self.stage_name}] 完成: attempts={attempts}, duration={duration_ms}ms")
        return result

    async def _call_llm(self, system: str, prompt: str) -> str:
        """調用 LLM 的通用方法。"""
        return await llm_client.analyze(prompt, system)
