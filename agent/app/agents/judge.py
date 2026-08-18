"""評委 AI — 對每個 AI 節點的輸出進行評分和質量把關。

評委職責:
1. 檢查輸出是否符合預期範式（JSON 格式、必要字段等）
2. 檢查內容質量（是否有實質分析、是否空洞、是否偏題）
3. 給出 0-100 評分和通過/不通過判定
4. 不通過時給出具體反饋，指導重生成

評委 prompt 按階段定制，每個階段有不同的預期範式。
"""
import json
import logging
from typing import Any

from app.core.llm_client import llm_client

logger = logging.getLogger("agent.judge")

# 各階段的預期範式描述
STAGE_EXPECTATIONS = {
    "market_news": {
        "format": "自然語言文本，包含市場情緒、利好行業、利空行業、選股建議",
        "required_content": "市場情緒判斷、利好行業列表、利空行業列表、選股建議",
        "min_length": 100,
    },
    "industry_analysis": {
        "format": "JSON，包含 reasoning、favorable_industries、filtered_codes 字段",
        "required_content": "分析理由 + 利好行業列表 + 篩選後股票代碼",
        "min_length": 80,
        "must_be_json": True,
        "required_fields": ["reasoning", "favorable_industries"],
    },
    "market_analysis": {
        "format": "自然語言文本，2-4 句話",
        "required_content": "市場趨勢判斷、波動率水平、適合的策略類型",
        "min_length": 50,
    },
    "strategy_generation": {
        "format": "JSON，包含 reasoning 和 criteria 字段",
        "required_content": "調整理由 + 完整的選股條件 JSON",
        "min_length": 100,
        "must_be_json": True,
        "required_fields": ["reasoning", "criteria"],
    },
    "backtest_reflection": {
        "format": "自然語言文本，結構化分析",
        "required_content": "策略優缺點、收益來源、風險控制、改進方向",
        "min_length": 100,
    },
    "prompt_generation": {
        "format": "自然語言文本，2-3 句話指引",
        "required_content": "下一輪應調整的參數、避免的策略、追求的目標",
        "min_length": 30,
    },
}

# 評委的 system prompt
JUDGE_SYSTEM = """你是一個嚴格的 AI 評委，負責評估 AI 節點的輸出質量。
你需要檢查：
1. 輸出是否符合預期的格式範式
2. 內容是否有實質分析（不是空洞的套話）
3. 內容是否與任務相關（不偏題）
4. 內容是否完整（包含所有必要信息）

評分標準：
- 90-100: 優秀，完全符合預期
- 70-89: 良好，基本符合預期，有小瑕疵
- 50-69: 及格，有問題但不影響後續流程
- 0-49: 不及格，需要重新生成

請嚴格按以下 JSON 格式返回：
```json
{
  "score": 85,
  "passed": true,
  "feedback": "評分理由和改進建議"
}
```"""

JUDGE_PROMPT_TEMPLATE = """請評估以下 AI 節點的輸出質量。

## 節點名稱
{stage_name}

## 預期範式
- 格式: {expected_format}
- 必須包含: {required_content}
- 最小長度: {min_length} 字符

## 實際輸出
{output}

## 你的任務
1. 檢查格式是否符合預期
2. 檢查內容是否包含所有必要信息
3. 檢查內容是否有實質分析（非空洞套話）
4. 給出評分和通過判定

請嚴格按 JSON 格式返回：
```json
{{
  "score": 85,
  "passed": true,
  "feedback": "評分理由"
}}
```"""


class JudgeAI:
    """評委 AI — 評估各節點輸出質量。"""

    def __init__(self, pass_threshold: float = 60.0):
        self.pass_threshold = pass_threshold

    async def evaluate(
        self,
        stage_name: str,
        output: str,
        context: dict[str, Any] = None,
    ) -> tuple[float, bool, str]:
        """評估節點輸出。

        Returns: (score, passed, feedback)
        """
        expectation = STAGE_EXPECTATIONS.get(stage_name)
        if not expectation:
            # 無預期範式的階段，直接通過
            return 100.0, True, "無預期範式，自動通過"

        # === 快速格式檢查（不調用 LLM） ===
        # 長度檢查
        if len(output.strip()) < expectation["min_length"]:
            return 20.0, False, f"輸出過短（{len(output.strip())} < {expectation['min_length']}字符），內容不充分"

        # JSON 格式檢查（如果要求 JSON）
        if expectation.get("must_be_json"):
            required_fields = expectation.get("required_fields", [])
            if not self._validate_json(output, required_fields):
                return 30.0, False, f"輸出不是有效的 JSON 格式，缺少必要字段: {required_fields}"

        # === LLM 評分 ===
        prompt = JUDGE_PROMPT_TEMPLATE.format(
            stage_name=stage_name,
            expected_format=expectation["format"],
            required_content=expectation["required_content"],
            min_length=expectation["min_length"],
            output=output[:2000],  # 截斷避免 token 過多
        )

        try:
            response = await llm_client.analyze(prompt, JUDGE_SYSTEM)
            score, passed, feedback = self._parse_judge_response(response)
            return score, passed, feedback
        except Exception as e:
            logger.warning(f"評委 LLM 調用失敗: {e}，使用格式檢查結果")
            # LLM 失敗時，基於格式檢查通過
            return 70.0, True, f"評委 LLM 不可用，格式檢查通過（{e}）"

    def _validate_json(self, output: str, required_fields: list[str] = None) -> bool:
        """快速驗證 JSON 輸出是否包含必要字段。

        Args:
            output: LLM 輸出文本
            required_fields: 必須包含的字段列表，空則只檢查是否為有效 JSON
        """
        try:
            # 嘗試提取 JSON
            json_start = output.find("```json")
            if json_start >= 0:
                json_start = output.find("{", json_start)
                json_end = output.rfind("}")
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(output[json_start:json_end + 1])
                else:
                    return False
            else:
                brace_start = output.find("{")
                brace_end = output.rfind("}")
                if brace_start >= 0 and brace_end > brace_start:
                    data = json.loads(output[brace_start:brace_end + 1])
                else:
                    return False

            # 檢查必要字段
            if required_fields:
                for field in required_fields:
                    if field not in data:
                        return False
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    def _parse_judge_response(self, response: str) -> tuple[float, bool, str]:
        """解析評委 LLM 的 JSON 響應。"""
        try:
            json_start = response.find("```json")
            if json_start >= 0:
                json_start = response.find("{", json_start)
                json_end = response.rfind("}")
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(response[json_start:json_end + 1])
                else:
                    raise ValueError("無 JSON")
            else:
                brace_start = response.find("{")
                brace_end = response.rfind("}")
                if brace_start >= 0 and brace_end > brace_start:
                    data = json.loads(response[brace_start:brace_end + 1])
                else:
                    raise ValueError("無 JSON")

            score = float(data.get("score", 50))
            passed = data.get("passed", score >= self.pass_threshold)
            feedback = data.get("feedback", "")
            return score, bool(passed), feedback
        except (json.JSONDecodeError, ValueError):
            # 解析失敗，保守通過
            logger.warning(f"評委響應解析失敗: {response[:100]}")
            return 60.0, True, "評委響應解析失敗，保守通過"
