"""JSON 提取工具 — 從 LLM 響應中穩健地提取 JSON，含多級降級策略。

問題：LLM 有時會在 JSON 前後加自然語言、markdown 標記、或多個 JSON 塊，
導致簡單的 find("{") → rfind("}") 策略失敗。

解決方案（多級降級）：
1. 嘗試直接 json.loads（理想情況：純 JSON）
2. 提取 ```json ... ``` 代碼塊
3. 用正則提取最外層 { ... }（處理嵌套）
4. 用正則逐個嘗試所有 { ... } 候選
5. 修正常見 JSON 格式錯誤（尾逗號、單引號、無引號 key）
6. 全部失敗 → 返回 None（調用方決定兜底策略）

使用方式：
    from app.utils.json_extractor import extract_json
    data = extract_json(llm_response)
    if data is None:
        # 走兜底邏輯
        data = default_criteria()
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger("agent.json_extractor")


def _try_parse(text: str) -> dict[str, Any] | None:
    """嘗試 json.loads，失敗返回 None。"""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
        return None
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_code_block(text: str) -> dict[str, Any] | None:
    """策略 2：提取 ```json ... ``` 代碼塊。"""
    # 匹配 ```json ... ``` 或 ``` ... ```
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    for m in matches:
        result = _try_parse(m)
        if result is not None:
            return result
    return None


def _extract_outermost_braces(text: str) -> dict[str, Any] | None:
    """策略 3：用棧匹配最外層 { ... }（處理嵌套）。"""
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                result = _try_parse(candidate)
                if result is not None:
                    return result
                # 嘗試修復後解析
                fixed = _fix_common_json_errors(candidate)
                if fixed:
                    result = _try_parse(fixed)
                    if result is not None:
                        return result
                break
    return None


def _extract_all_candidates(text: str) -> dict[str, Any] | None:
    """策略 4：逐個嘗試所有 { ... } 候選（從長到短）。"""
    # 找到所有 { 的位置
    brace_starts = [i for i, ch in enumerate(text) if ch == "{"]
    if not brace_starts:
        return None

    # 從最長候選開始嘗試（最可能是完整 JSON）
    candidates = []
    for start in brace_starts:
        # 找到對應的結束 }
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break

    # 按長度降序排列（長的更可能是完整 JSON）
    candidates.sort(key=len, reverse=True)
    for c in candidates:
        result = _try_parse(c)
        if result is not None:
            return result
        # 嘗試修復
        fixed = _fix_common_json_errors(c)
        if fixed:
            result = _try_parse(fixed)
            if result is not None:
                logger.debug(f"JSON 提取成功（修復後）: {list(result.keys())}")
                return result

    return None


def _fix_common_json_errors(text: str) -> str | None:
    """策略 5：修正常見 JSON 格式錯誤。

    處理：
    - 尾逗號（trailing comma）
    - 單引號 → 雙引號
    - 無引號的 key
    - 布爾值首字母大寫（True/False → true/false）
    - None → null
    """
    fixed = text

    # 移除尾逗號（}, ] 前的逗號）
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

    # True/False/None → true/false/null（Python 風格 → JSON）
    fixed = re.sub(r"\bTrue\b", "true", fixed)
    fixed = re.sub(r"\bFalse\b", "false", fixed)
    fixed = re.sub(r"\bNone\b", "null", fixed)

    # 單引號 → 雙引號（簡單替換，可能有邊界情況但作為降級可接受）
    if "'" in fixed and '"' not in fixed:
        fixed = fixed.replace("'", '"')

    # 無引號的 key（如 {reasoning: "..."} → {"reasoning": "..."}）
    fixed = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', fixed)

    return fixed


def extract_json(response: str) -> dict[str, Any] | None:
    """從 LLM 響應中穩健地提取 JSON 對象。

    多級降級策略：
    1. 直接解析（純 JSON）
    2. ```json 代碼塊
    3. 棧匹配最外層 { ... }
    4. 逐個嘗試所有 { ... } 候選
    5. 修復常見錯誤後重試

    Args:
        response: LLM 響應文本

    Returns:
        dict | None: 解析出的 dict，或 None（全部失敗）
    """
    if not response or not isinstance(response, str):
        return None

    text = response.strip()

    # 策略 1：直接解析
    result = _try_parse(text)
    if result is not None:
        return result

    # 策略 2：```json 代碼塊
    result = _extract_code_block(text)
    if result is not None:
        return result

    # 策略 3：棧匹配最外層
    result = _extract_outermost_braces(text)
    if result is not None:
        return result

    # 策略 4+5：逐個候選 + 修復
    result = _extract_all_candidates(text)
    if result is not None:
        return result

    logger.warning(f"JSON 提取失敗（所有策略均未成功）: {text[:200]}")
    return None


def extract_json_with_fallback(
    response: str,
    fallback: dict[str, Any] | None = None,
    required_fields: list[str] | None = None,
) -> dict[str, Any]:
    """從 LLM 響應中提取 JSON，失敗時返回兜底值。

    Args:
        response: LLM 響應文本
        fallback: 兜底 dict（默認空 dict）
        required_fields: 必須包含的字段（缺失時用兜底值填充）

    Returns:
        dict: 解析出的 dict 或兜底值
    """
    if fallback is None:
        fallback = {}

    data = extract_json(response)
    if data is None:
        logger.warning("JSON 提取失敗，使用兜底值")
        return fallback

    # 補齊缺失的必要字段
    if required_fields:
        for field in required_fields:
            if field not in data:
                logger.debug(f"JSON 缺少字段 {field}，用兜底值填充")
                data[field] = fallback.get(field)

    return data
