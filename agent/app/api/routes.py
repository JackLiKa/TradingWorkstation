"""FastAPI 路由層 — 對外 REST 接口。"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.optimizer import state, start_optimization, stop_optimization
from app.core.llm_client import llm_client

logger = logging.getLogger("agent.api")

router = APIRouter()


class StartRequest(BaseModel):
    """啟動優化請求。"""
    criteria: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


class UpdateCriteriaRequest(BaseModel):
    """更新選股條件請求。"""
    criteria: dict[str, Any]


@router.get("/health")
async def health():
    """健康檢查 — 返回服務狀態、後端可用性和當前 LLM 模型信息。

    Returns:
        dict: 包含 status / backend_available / model 三個維度的健康信息
    """
    from app.services.backend_client import backend_client
    backend_ok = await backend_client.health()
    return {
        "status": "ok",
        "backend_available": backend_ok,
        "model": {
            "provider": llm_client.model_status.provider,
            "model_name": llm_client.model_status.model_name,
            "available": llm_client.model_status.available,
            "is_free": llm_client.model_status.is_free,
            "last_check": llm_client.model_status.last_check,
            "error": llm_client.model_status.error,
        },
    }


@router.post("/start")
async def start(req: StartRequest | None = None):
    """啟動 AI 優化循環。

    Args:
        req: 可選的啟動請求，可攜帶用戶自定義的初始選股條件和回測配置；
             為 None 時使用默認或數據庫最佳策略

    Returns:
        dict: 啟動結果（started / already_running）及當前狀態快照
    """
    if state.running:
        return {"status": "already_running", "state": state.to_dict()}

    # 可選：使用用戶提供的初始條件（與默認值合併，用戶值優先）
    if req and req.criteria:
        from app.agents.optimizer import DEFAULT_CRITERIA
        state.current_criteria = {**DEFAULT_CRITERIA, **req.criteria}
    if req and req.config:
        from app.agents.optimizer import DEFAULT_BACKTEST_CONFIG
        state.current_config = {**DEFAULT_BACKTEST_CONFIG, **req.config}

    start_optimization()
    return {"status": "started", "state": state.to_dict()}


@router.post("/stop")
async def stop():
    """停止 AI 優化循環。

    Returns:
        dict: 停止中狀態及當前狀態快照
    """
    stop_optimization()
    return {"status": "stopping", "state": state.to_dict()}


@router.get("/status")
async def get_status():
    """獲取當前優化狀態（運行狀態、當前參數、歷史摘要、模型狀態）。

    Returns:
        dict: 優化器完整狀態的序列化字典
    """
    return state.to_dict()


@router.get("/history")
async def get_history(limit: int = 20):
    """獲取優化歷史記錄。

    Args:
        limit: 返回最近多少輪迭代記錄，默認 20

    Returns:
        dict: 包含 total（總輪數）和 iterations（迭代列表，倒序）
    """
    iterations = state.iterations[-limit:]
    return {
        "total": len(state.iterations),
        "iterations": [it.to_dict() for it in reversed(iterations)],
    }


@router.get("/history/{iteration}")
async def get_iteration(iteration: int):
    """獲取特定輪次的詳細結果。

    Args:
        iteration: 迭代輪次編號

    Returns:
        dict: 該輪次的完整 IterationResult

    Raises:
        HTTPException: 404 — 指定迭代輪次不存在
    """
    for it in state.iterations:
        if it.iteration == iteration:
            return it.to_dict()
    raise HTTPException(status_code=404, detail=f"迭代 {iteration} 不存在")


@router.post("/criteria")
async def update_criteria(req: UpdateCriteriaRequest):
    """手動更新當前選股條件（不影響正在運行的循環的下一輪）。

    Args:
        req: 包含新選股條件的請求體

    Returns:
        dict: 更新結果及合併後的完整選股條件
    """
    from app.agents.optimizer import DEFAULT_CRITERIA
    state.current_criteria = {**DEFAULT_CRITERIA, **req.criteria}
    return {"status": "updated", "criteria": state.current_criteria}


@router.get("/criteria")
async def get_criteria():
    """獲取當前選股條件和回測配置。

    Returns:
        dict: 包含 criteria 和 config 兩個字段
    """
    return {"criteria": state.current_criteria, "config": state.current_config}


@router.post("/model/check")
async def check_model():
    """手動觸發 LLM 模型可用性檢查。

    Returns:
        dict: 模型狀態（provider / model_name / available / last_check / error）
    """
    status = await llm_client.check_models()
    return {
        "provider": status.provider,
        "model_name": status.model_name,
        "available": status.available,
        "last_check": status.last_check,
        "error": status.error,
    }


# ===== 監控端點 =====

@router.get("/monitor")
async def get_monitor_status():
    """獲取監控狀態（節點事件 + 告警 + 統計）。

    Returns:
        dict: 監控器狀態摘要，含事件列表、告警列表和節點統計
    """
    from app.agents.monitor import node_monitor
    return node_monitor.get_status()


@router.get("/monitor/analyze")
async def analyze_monitor():
    """監測 AI 分析當前系統狀態 — 調用 LLM 分析異常並給出建議。

    Returns:
        dict: 包含 analysis（AI 分析文本）、health（健康狀態）、suggestions（建議列表）
    """
    from app.agents.monitor_ai import monitor_ai
    return await monitor_ai.analyze()


@router.post("/monitor/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """標記告警為已解決。

    Args:
        alert_id: 告警的唯一標識符

    Returns:
        dict: 解決結果確認
    """
    from app.agents.monitor import node_monitor
    node_monitor.resolve_alert(alert_id)
    return {"status": "resolved", "alert_id": alert_id}
