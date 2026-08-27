"""安全後處理器 — 對 AI 輸出做安全審查和投資建議攔截。

職責：
- 攔截直接投資建議（「建議買入」「目標價 XX」等）
- 添加免責聲明
- 檢測 prompt injection 風險（AI 輸出中嵌入的指令）
- 記錄安全事件到日誌

設計要點：
- 純函數，無副作用，不改變 AI 輸出的策略邏輯
- 只攔截「面向用戶」的自然語言輸出，不攔截 JSON 結構化數據
- 自動降級：審查失敗時放行原文本，不影響優化循環
"""

import logging
import re
from typing import Any

logger = logging.getLogger("agent.safety")

# ===== 投資建議攔截模式 =====
# 匹配直接投資建議的關鍵詞模式
_INVESTMENT_ADVICE_PATTERNS = [
    # 直接買賣建議
    re.compile(r"(建議|推薦|應該|請)(買入|賣出|加倉|減倉|清倉|建倉|持有)", re.IGNORECASE),
    # 目標價
    re.compile(r"目標價\s*[:：]?\s*\d+\.?\d*", re.IGNORECASE),
    # 止盈/止損具體價位建議
    re.compile(r"(止盈|止損)\s*[:：]?\s*\d+\.?\d*\s*(元|塊)", re.IGNORECASE),
    # 「強烈推薦」「強力買入」等
    re.compile(r"(強烈推薦|強力買入|強烈建議|強烈看漲|強烈看跌)", re.IGNORECASE),
    # 「一定會漲」「保證收益」等承諾性語言
    re.compile(r"(一定會|肯定會|保證|必定|穩賺|穩贏|零風險|無風險)", re.IGNORECASE),
]

# ===== Prompt Injection 檢測模式 =====
# 檢測 AI 輸出中可能嵌入的惡意指令
_INJECTION_PATTERNS = [
    # 忽略先前指令
    re.compile(r"(ignore|disregard).*(previous|prior|above).*(instruction|prompt|rule)", re.IGNORECASE),
    # 角色扮演越獄
    re.compile(r"(you are now|act as|pretend to be).*(developer|admin|root|system)", re.IGNORECASE),
    # 嘗試獲取系統信息
    re.compile(r"(show|reveal|print|output).*(api.?key|password|secret|token|env)", re.IGNORECASE),
]

# 免責聲明（附加到面向用戶的輸出末尾）
DISCLAIMER = "\n\n---\n⚠️ 免責聲明：本系統輸出僅供研究參考，不構成任何投資建議。使用者應自行判斷投資風險。"


def scan_text(text: str) -> dict[str, Any]:
    """掃描文本中的投資建議和 prompt injection 風險。

    Args:
        text: 待審查的文本（AI 自然語言輸出）

    Returns:
        dict: 審查結果，包含：
            - has_investment_advice: bool — 是否檢測到投資建議
            - has_injection_risk: bool — 是否檢測到 prompt injection
            - matched_patterns: list[str] — 匹配到的模式描述
            - risk_level: str — "none" / "low" / "high"
    """
    matched = []
    has_advice = False
    has_injection = False

    for pattern in _INVESTMENT_ADVICE_PATTERNS:
        m = pattern.search(text)
        if m:
            has_advice = True
            matched.append(f"投資建議: {m.group()}")

    for pattern in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            has_injection = True
            matched.append(f"注入風險: {m.group()}")

    if has_injection:
        risk_level = "high"
    elif has_advice:
        risk_level = "low"
    else:
        risk_level = "none"

    return {
        "has_investment_advice": has_advice,
        "has_injection_risk": has_injection,
        "matched_patterns": matched,
        "risk_level": risk_level,
    }


def sanitize_output(text: str, add_disclaimer: bool = True) -> str:
    """對 AI 面向用戶的自然語言輸出做安全後處理。

    - 攔截投資建議：替換為中性表述
    - 檢測 prompt injection：記錄警告（不刪除，因為可能是誤報）
    - 添加免責聲明

    Args:
        text: AI 輸出的自然語言文本
        add_disclaimer: 是否添加免責聲明

    Returns:
        str: 處理後的安全文本
    """
    if not text or not isinstance(text, str):
        return text

    result = scan_text(text)

    # 記錄安全事件
    if result["matched_patterns"]:
        for pattern_desc in result["matched_patterns"]:
            if result["has_injection_risk"]:
                logger.warning(f"安全告警 — prompt injection 風險: {pattern_desc}")
            else:
                logger.info(f"安全提示 — 投資建議檢測: {pattern_desc}")

    # 高風險（prompt injection）：記錄但不自動刪除，由 Judge 評委判定
    if result["has_injection_risk"]:
        logger.warning("檢測到 prompt injection 風險，已記錄。Judge 評委將判定是否拒絕該輸出。")

    # 低風險（投資建議）：替換為中性表述
    sanitized = text
    if result["has_investment_advice"]:
        # 替換直接買賣建議為中性分析表述
        sanitized = re.sub(
            r"(建議|推薦|應該|請)(買入|賣出|加倉|減倉|清倉|建倉)",
            "分析顯示可能適合",
            sanitized,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(
            r"(強烈推薦|強力買入|強烈建議|強烈看漲|強烈看跌)",
            "數據顯示較強信號",
            sanitized,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(
            r"(一定會|肯定會|保證|必定|穩賺|穩贏|零風險|無風險)",
            "歷史數據顯示",
            sanitized,
            flags=re.IGNORECASE,
        )
        # 移除目標價具體數值（替換為佔位）
        sanitized = re.sub(
            r"目標價\s*[:：]?\s*\d+\.?\d*",
            "目標價：[需用戶自行判斷]",
            sanitized,
            flags=re.IGNORECASE,
        )
        logger.info("已將投資建議替換為中性分析表述")

    # 添加免責聲明
    if add_disclaimer and DISCLAIMER not in sanitized:
        sanitized += DISCLAIMER

    return sanitized


def check_json_output(json_str: str) -> dict[str, Any]:
    """檢查 JSON 格式的 AI 輸出是否包含安全風險。

    JSON 輸出不做文本替換（因為會破壞結構），
    只做風險檢測並記錄，由 Judge 評委判定。

    Args:
        json_str: AI 輸出的 JSON 字符串

    Returns:
        dict: 審查結果（同 scan_text 返回結構）
    """
    if not json_str or not isinstance(json_str, str):
        return {
            "has_investment_advice": False,
            "has_injection_risk": False,
            "matched_patterns": [],
            "risk_level": "none",
        }

    result = scan_text(json_str)
    if result["matched_patterns"]:
        for pattern_desc in result["matched_patterns"]:
            logger.info(f"JSON 輸出安全檢查: {pattern_desc}")
    return result
