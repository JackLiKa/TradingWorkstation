"""錯誤/重試經驗持久化存儲 — 記錄 AI 階段失敗和重試，供後續優化復用。

職責：
- 記錄每個 AI 階段的錯誤、重試、JSON 提取失敗等事件
- 持久化到 JSON 文件（agent/data/error_experiences.json）
- 按階段名 + 錯誤類型分類，支持查詢
- 在策略生成階段注入「歷史錯誤教訓」到 prompt，避免重複犯錯
- 自動降級：文件不可寫時只記日誌，不影響優化循環

存儲格式（JSON 文件）：
{
  "errors": [
    {
      "id": "err_001",
      "timestamp": "2026-08-20T22:00:00",
      "run_id": "run_20260820_220000",
      "iteration": 3,
      "stage_name": "strategy_generation",
      "error_type": "json_extraction",  # json_extraction | llm_call | judge_rejection | other
      "error_message": "無法從 LLM 響應中提取 JSON: ...",
      "raw_output_preview": "前 500 字符的 LLM 輸出",
      "attempts": 2,
      "provider": "glm-flash",
      "recovered": true,  # 是否最終恢復（重試成功或降級兜底）
      "recovery_method": "retry"  # retry | fallback | default | none
    }
  ]
}
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("agent.error_store")

# 存儲路徑
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_STORE_FILE = _DATA_DIR / "error_experiences.json"

# 保留上限（避免無限增長）
_MAX_ERRORS = 200

# 線程安全鎖
_lock = threading.Lock()

# 內存緩存（啟動時加載）
_cache: list[dict[str, Any]] = []
_loaded = False


def _ensure_loaded():
    """延遲加載錯誤記錄到內存緩存。"""
    global _loaded, _cache
    if _loaded:
        return
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        if _STORE_FILE.exists():
            with open(_STORE_FILE, encoding="utf-8") as f:
                data = json.load(f)
                _cache = data.get("errors", [])
        _loaded = True
        logger.debug(f"錯誤經驗庫已加載: {_cache.__len__()} 條記錄")
    except Exception as e:
        logger.warning(f"載入錯誤經驗庫失敗（忽略）: {e}")
        _cache = []
        _loaded = True


def _persist():
    """將內存緩存持久化到文件。"""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump({"errors": _cache}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"持久化錯誤經驗失敗（忽略）: {e}")


def record_error(
    stage_name: str,
    error_type: str,
    error_message: str,
    raw_output_preview: str = "",
    iteration: int = 0,
    run_id: str = "",
    attempts: int = 1,
    provider: str = "",
    recovered: bool = False,
    recovery_method: str = "none",
) -> str:
    """記錄一條錯誤經驗。

    Args:
        stage_name: 階段名（如 strategy_generation）
        error_type: 錯誤類型（json_extraction | llm_call | judge_rejection | other）
        error_message: 錯誤信息
        raw_output_preview: LLM 原始輸出預覽（前 500 字符）
        iteration: 迭代輪次
        run_id: 運行 ID
        attempts: 嘗試次數
        provider: 使用的 LLM 供應商
        recovered: 是否最終恢復
        recovery_method: 恢復方式（retry | fallback | default | none）

    Returns:
        str: 錯誤記錄 ID
    """
    _ensure_loaded()
    global _cache
    error_id = f"err_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(_cache) % 10000:04d}"

    record = {
        "id": error_id,
        "timestamp": datetime.now().isoformat(),
        "run_id": run_id,
        "iteration": iteration,
        "stage_name": stage_name,
        "error_type": error_type,
        "error_message": error_message[:500],
        "raw_output_preview": raw_output_preview[:500],
        "attempts": attempts,
        "provider": provider,
        "recovered": recovered,
        "recovery_method": recovery_method,
    }

    with _lock:
        _cache.append(record)
        # 保留上限：刪除最舊的
        if len(_cache) > _MAX_ERRORS:
            _cache = _cache[-_MAX_ERRORS:]
        _persist()

    logger.info(f"錯誤經驗已記錄: {error_id} (stage={stage_name}, type={error_type}, recovered={recovered})")
    return error_id


def get_errors_by_stage(stage_name: str, limit: int = 10) -> list[dict[str, Any]]:
    """獲取指定階段的歷史錯誤記錄。

    Args:
        stage_name: 階段名
        limit: 最多返回條數

    Returns:
        list[dict]: 錯誤記錄列表（按時間倒序）
    """
    _ensure_loaded()
    with _lock:
        stage_errors = [e for e in _cache if e["stage_name"] == stage_name]
    return stage_errors[-limit:][::-1]


def get_errors_by_type(error_type: str, limit: int = 10) -> list[dict[str, Any]]:
    """獲取指定類型的歷史錯誤記錄。"""
    _ensure_loaded()
    with _lock:
        typed_errors = [e for e in _cache if e["error_type"] == error_type]
    return typed_errors[-limit:][::-1]


def format_errors_for_prompt(stage_name: str, limit: int = 5) -> str:
    """將歷史錯誤格式化為可注入 prompt 的文本。

    在策略生成等階段注入，幫助 AI 避免重複犯錯。

    Args:
        stage_name: 階段名
        limit: 最多引用條數

    Returns:
        str: 格式化的錯誤教訓文本（空字符串表示無記錄）
    """
    errors = get_errors_by_stage(stage_name, limit)
    if not errors:
        return ""

    lines = [f"## 歷史錯誤教訓（{stage_name} 階段，共 {len(errors)} 條）"]
    for i, err in enumerate(errors, 1):
        recovered_tag = "✓已恢復" if err["recovered"] else "✗未恢復"
        lines.append(f"### 教訓{i}（{err['error_type']}，{recovered_tag}，{err['timestamp'][:10]}）")
        lines.append(f"- 錯誤: {err['error_message'][:200]}")
        if err["raw_output_preview"]:
            lines.append(f"- 原始輸出片段: {err['raw_output_preview'][:150]}...")
        if err["recovered"] and err["recovery_method"]:
            lines.append(f"- 恢復方式: {err['recovery_method']}")

    lines.append("")
    lines.append("請避免重複以上錯誤：")
    lines.append("- 如果是 JSON 格式錯誤，確保輸出嚴格遵循 JSON 語法")
    lines.append("- 如果是內容質量問題，確保引用輸入數據而非編造")

    return "\n".join(lines)


def get_all_errors(limit: int = 100) -> list[dict[str, Any]]:
    """獲取全部錯誤記錄（按時間倒序）。"""
    _ensure_loaded()
    with _lock:
        return _cache[-limit:][::-1]


def get_error_stats() -> dict[str, Any]:
    """獲取錯誤統計摘要。"""
    _ensure_loaded()
    with _lock:
        total = len(_cache)
        if total == 0:
            return {"total": 0, "by_stage": {}, "by_type": {}, "recovery_rate": 0}

        by_stage: dict[str, int] = {}
        by_type: dict[str, int] = {}
        recovered_count = 0
        for e in _cache:
            by_stage[e["stage_name"]] = by_stage.get(e["stage_name"], 0) + 1
            by_type[e["error_type"]] = by_type.get(e["error_type"], 0) + 1
            if e["recovered"]:
                recovered_count += 1

        return {
            "total": total,
            "by_stage": by_stage,
            "by_type": by_type,
            "recovery_rate": round(recovered_count / total * 100, 1),
            "store_file": str(_STORE_FILE),
        }


def clear_errors() -> int:
    """清空錯誤記錄（返回清空的條數）。"""
    global _cache
    _ensure_loaded()
    with _lock:
        count = len(_cache)
        _cache = []
        _persist()
    logger.info(f"已清空 {count} 條錯誤記錄")
    return count
