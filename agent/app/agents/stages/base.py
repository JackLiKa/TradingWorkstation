"""AI 節點基類 — AOP 鉤子 + JSON 標準化 + 可觀測性 + 評委集成 + 調用日誌。

AOP 鉤子:
- pre_execute: 執行前（更新狀態、日誌）
- execute: 實際 AI 調用（子類實現）
- post_execute: 執行後（記錄耗時、更新狀態、寫入 ai_call_log）
- on_error: 異常處理

JSON 標準化（多重約束）:
- 每次調用構建標準化 input JSON：{system_prompt, user_prompt, context, provider, model, timestamp}
- 每次調用構建標準化 output JSON：{raw_text, parsed, provider, model, duration_ms, fallback_from}
- 調用完成後寫入後端 ai_call_log 表

可觀測性:
- 記錄每個階段的開始/結束時間、耗時、嘗試次數、評委結果、供應商、降級信息
- 通過 stage_name 和 status 追蹤節點狀態
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from app.agents.state import StageResult
from app.agents.monitor import node_monitor
from app.agents.charter import get_charter
from app.core.llm_client import llm_client, LLMResponse

logger = logging.getLogger("agent.stage")


class BaseStage(ABC):
    """AI 節點基類 — 子類實現 build_prompt 和 execute。"""

    def __init__(self, stage_name: str, display_name: str):
        self.stage_name = stage_name
        self.display_name = display_name
        self._current_iteration = 1  # 當前迭代輪次（供 _call_llm 注入憲章）
        self._last_llm_response = None  # LLM 響應緩存

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """執行 AI 調用，返回原始輸出。子類實現。"""
        ...

    def get_system_prompt(self) -> str:
        """返回該階段的 system prompt（子類可覆蓋）。"""
        return "你是一個專業的 AI 助手。"

    def get_full_system_prompt(self, iteration: int = 1) -> str:
        """返回含憲章的完整 system prompt。

        第一輪注入完整憲章（身份/職責/約束/IO標準）；
        後續輪次注入回憶摘要，避免上下文過長造成的失憶或風格漂移。
        """
        charter = get_charter(iteration)
        base_prompt = self.get_system_prompt()
        return f"{charter}\n\n---\n\n## 本節點職責\n{base_prompt}"

    def build_user_prompt(self, **kwargs) -> str:
        """構建用戶提示詞（子類實現）。"""
        return ""

    def build_context(self, **kwargs) -> dict:
        """構建上下文元數據（子類可覆蓋）。"""
        # 默認：序列化 kwargs 為可 JSON 化的字典
        ctx = {}
        for k, v in kwargs.items():
            try:
                json.dumps(v, ensure_ascii=False, default=str)
                ctx[k] = v
            except (TypeError, ValueError):
                ctx[k] = str(v)
        return ctx

    def get_preferred_provider(self) -> str:
        """獲取本階段偏好的供應商（可被子類覆蓋或通過全局配置覆蓋）。

        優先級：
        1. 用戶通過 API 設置的 stage_providers[stage_name]
        2. 階段默認供應商（providers.STAGE_DEFAULT_PROVIDERS）
        """
        from app.core.config import settings
        from app.core.providers import get_default_provider_for_stage
        user_pref = settings.stage_providers.get(self.stage_name, "")
        if user_pref:
            return user_pref
        return get_default_provider_for_stage(self.stage_name)

    async def run(self, state, judge=None, max_attempts: int = 2, **kwargs) -> StageResult:
        """執行完整流程：pre → execute → judge → post → log。

        AOP 鉤子：
        - pre_execute: 更新狀態為 running
        - execute: 調用 AI（含 JSON 標準化）
        - judge: 評委評分（如果有）
        - post_execute: 記錄結果 + 寫入 ai_call_log
        - 如果評委不通過且未達最大嘗試次數，重試
        """
        start_time = time.time()
        attempts = 0
        last_output = ""
        last_error = None
        judge_score = 0.0
        judge_passed = True
        judge_feedback = ""
        last_llm_response: Optional[LLMResponse] = None
        last_input_json = ""
        self._last_llm_response = None  # 供 _call_llm 緩存
        self._current_iteration = state.current_iteration + 1  # 供 _call_llm 注入憲章

        system_prompt = self.get_full_system_prompt(iteration=state.current_iteration + 1)
        user_prompt = self.build_user_prompt(**kwargs)
        context = self.build_context(**kwargs)
        preferred_provider = self.get_preferred_provider()

        # 構建標準化 input JSON
        standard_input = {
            "schema_version": "1.0",
            "stage_name": self.stage_name,
            "stage_display_name": self.display_name,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "context": context,
            "preferred_provider": preferred_provider,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            last_input_json = json.dumps(standard_input, ensure_ascii=False, default=str)
        except Exception:
            last_input_json = json.dumps({"error": "input serialization failed", "stage_name": self.stage_name})

        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            state.current_stage = self.stage_name
            state.current_stage_status = "running"
            if attempt == 1:
                node_monitor.record_start(self.stage_name, node_type="ai")
            logger.info(f"[{self.stage_name}] 第 {attempt} 次嘗試 (provider偏好: {preferred_provider or 'auto'})")

            try:
                # === execute ===
                self._last_llm_response = None  # 重置本次嘗試的 LLM 響應緩存
                last_output = await self.execute(**kwargs)
                last_error = None
                # 從 _call_llm 緩存中讀取 LLM 響應元數據
                if self._last_llm_response is not None:
                    last_llm_response = self._last_llm_response

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

        # 構建標準化 output JSON
        standard_output = {
            "schema_version": "1.0",
            "stage_name": self.stage_name,
            "raw_text": last_output,
            "parsed": None,  # 子類可覆蓋 parse_output
            "provider": last_llm_response.provider if last_llm_response else "unknown",
            "model_name": last_llm_response.model_name if last_llm_response else "unknown",
            "duration_ms": duration_ms,
            "fallback_from": last_llm_response.fallback_from if last_llm_response else "",
            "attempts": attempts,
            "judge_score": judge_score,
            "judge_passed": judge_passed,
        }
        try:
            last_output_json = json.dumps(standard_output, ensure_ascii=False, default=str)
        except Exception:
            last_output_json = json.dumps({"error": "output serialization failed"})

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

        # === 寫入 ai_call_log（後端數據庫）===
        await self._log_to_backend(
            state=state,
            input_json=last_input_json,
            output_text=last_output,
            output_json=last_output_json,
            judge_score=judge_score,
            judge_passed=judge_passed,
            judge_feedback=judge_feedback,
            attempts=attempts,
            duration_ms=duration_ms,
            error=last_error,
            llm_response=last_llm_response,
        )

        logger.info(f"[{self.stage_name}] 完成: attempts={attempts}, duration={duration_ms}ms")
        return result

    async def _call_llm(self, system: str, prompt: str, json_mode: bool = False) -> str:
        """調用 LLM 的通用方法 — 支持每階段供應商選擇 + 記錄響應元數據。

        注意：此方法會緩存 LLMResponse 到實例，供 run() 寫入日誌使用。
        如果 system 傳入的是子類的短版 SYSTEM_PROMPT，會自動替換為含憲章的完整版。

        Args:
            system: 系統提示詞
            prompt: 用戶提示詞
            json_mode: 是否啟用 JSON 結構化輸出（用於需要 JSON 的階段）
        """
        preferred = self.get_preferred_provider()
        # 如果傳入的 system 與子類的 get_system_prompt() 相同，替換為含憲章的完整版
        if system == self.get_system_prompt():
            system = self.get_full_system_prompt(iteration=self._current_iteration)
        response = await llm_client.analyze(prompt, system, preferred_provider=preferred, json_mode=json_mode)
        # 緩存到實例供 run() 讀取
        self._last_llm_response = response
        return response.text

    async def _log_to_backend(
        self,
        state,
        input_json: str,
        output_text: str,
        output_json: str,
        judge_score: float,
        judge_passed: bool,
        judge_feedback: str,
        attempts: int,
        duration_ms: int,
        error: Optional[str],
        llm_response: Optional[LLMResponse],
    ):
        """將本次調用寫入後端 ai_call_log 表。"""
        try:
            from app.services.backend_client import backend_client
            iteration = state.current_iteration + 1
            provider = llm_response.provider if llm_response else "unknown"
            model_name = llm_response.model_name if llm_response else "unknown"
            await backend_client.log_ai_call(
                iteration=iteration,
                stage_name=self.stage_name,
                stage_display_name=self.display_name,
                provider=provider,
                model_name=model_name,
                input_json=input_json,
                output_text=output_text,
                output_json=output_json,
                judge_score=judge_score,
                judge_passed=judge_passed,
                judge_feedback=judge_feedback,
                attempts=attempts,
                duration_ms=duration_ms,
                error=error,
            )
        except Exception as e:
            logger.warning(f"[{self.stage_name}] 寫入 ai_call_log 失敗: {e}")
