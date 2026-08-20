"""FastAPI 路由層 — 對外 REST 接口。"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.agents.optimizer import start_optimization, state, stop_optimization
from app.core.llm_client import llm_client
from app.core.metrics import render_prometheus_metrics

logger = logging.getLogger("agent.api")

router = APIRouter()


class StartRequest(BaseModel):
    """啟動優化請求。"""

    criteria: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


class UpdateCriteriaRequest(BaseModel):
    """更新選股條件請求。"""

    criteria: dict[str, Any]


class UpdateConfigRequest(BaseModel):
    """更新回測配置請求（支持手動調整回測日期區間等）。"""

    config: dict[str, Any]


def _validate_backtest_dates(
    config: dict[str, Any],
    earliest: str | None,
    latest: str | None,
) -> tuple[bool, str]:
    """校驗回測日期區間是否在數據庫覆蓋範圍內。

    Args:
        config: 回測配置，需包含 startDate 和 endDate
        earliest: 數據庫最早交易日（YYYY-MM-DD），None 表示無法獲取
        latest: 數據庫最新交易日（YYYY-MM-DD），None 表示無法獲取

    Returns:
        tuple[bool, str]: (是否通過, 錯誤消息)，通過時錯誤消息為空字符串
    """
    start = config.get("startDate")
    end = config.get("endDate")
    if not start or not end:
        return False, "回測配置必須包含 startDate 和 endDate"
    if start > end:
        return False, f"startDate ({start}) 不能晚於 endDate ({end})"
    if earliest and start < earliest:
        return False, f"startDate ({start}) 早於數據庫最早交易日 ({earliest})，請確保數據存在"
    if latest and end > latest:
        return False, f"endDate ({end}) 晚於數據庫最新交易日 ({latest})，請確保數據存在"
    return True, ""


@router.get("/health")
async def health():
    """健康檢查 — 返回服務狀態、後端可用性、LLM 模型信息和 RAG 狀態。

    Returns:
        dict: 包含 status / backend_available / model / models / rag 五個維度的健康信息
              status: "ok"（服務存活）或 "degraded"（後端不可用）
              model: 當前選中的供應商狀態（向後兼容）
              models: 全部供應商的檢查結果列表
              rag: RAG 向量數據庫狀態
    """
    import asyncio

    from app.services.backend_client import backend_client
    from app.services.experience_store import get_rag_status

    # 帶超時的後端健康檢查（防止掛起）
    try:
        backend_ok = await asyncio.wait_for(backend_client.health(), timeout=5.0)
    except asyncio.TimeoutError:
        backend_ok = False

    # RAG 狀態
    rag_status = get_rag_status()

    # 速率限制狀態
    from app.core.rate_limiter import get_status as get_rate_limit_status

    rate_limit_status = get_rate_limit_status()

    # 配置概覽
    from app.core.config import settings

    config_overview = settings.to_dict()

    return {
        "status": "ok" if backend_ok else "degraded",
        "backend_available": backend_ok,
        "model": {
            "provider": llm_client.model_status.provider,
            "model_name": llm_client.model_status.model_name,
            "available": llm_client.model_status.available,
            "is_free": llm_client.model_status.is_free,
            "last_check": llm_client.model_status.last_check,
            "error": llm_client.model_status.error,
        },
        "models": llm_client.get_all_model_statuses(),
        "rag": rag_status,
        "rate_limits": rate_limit_status,
        "config": config_overview,
    }


@router.get("/metrics")
async def metrics():
    """Prometheus 指標端點 — 供 Prometheus 抓取。

    返回 Prometheus 文本格式指標，包含：
    - 優化迭代數和評分
    - 各階段耗時和評委評分
    - LLM 調用數/耗時/降級
    - RAG 操作數/耗時
    - 後端 API 調用數/錯誤/重試
    """
    return Response(
        content=render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.post("/start")
async def start(req: StartRequest | None = None):
    """啟動 AI 優化循環。

    Args:
        req: 可選的啟動請求，可攜帶用戶自定義的初始選股條件和回測配置；
             為 None 時使用默認或數據庫最佳策略。
             config 中的 startDate/endDate 會校驗是否在數據庫覆蓋範圍內。

    Returns:
        dict: 啟動結果（started / already_running / error）及當前狀態快照

    Raises:
        HTTPException: 400 — 回測日期區間不在數據庫覆蓋範圍內
    """
    if state.running:
        return {"status": "already_running", "state": state.to_dict()}

    # 可選：使用用戶提供的初始條件（與默認值合併，用戶值優先）
    if req and req.criteria:
        from app.agents.optimizer import DEFAULT_CRITERIA

        state.current_criteria = {**DEFAULT_CRITERIA, **req.criteria}
    if req and req.config:
        from app.agents.optimizer import DEFAULT_BACKTEST_CONFIG

        merged_config = {**DEFAULT_BACKTEST_CONFIG, **req.config}
        # 校驗回測日期區間是否在數據庫覆蓋範圍內
        from app.services.backend_client import backend_client

        earliest, latest = await backend_client.get_data_range()
        ok, msg = _validate_backtest_dates(merged_config, earliest, latest)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        state.current_config = merged_config

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


@router.post("/config")
async def update_config(req: UpdateConfigRequest):
    """手動更新回測配置（支持調整回測日期區間、持倉數、調倉間隔等）。

    日期區間會校驗是否在數據庫覆蓋範圍內，確保回測基於真實數據。

    Args:
        req: 包含新回測配置的請求體，需包含 startDate 和 endDate

    Returns:
        dict: 更新結果及合併後的完整回測配置

    Raises:
        HTTPException: 400 — 日期區間不在數據庫覆蓋範圍內
    """
    from app.agents.optimizer import DEFAULT_BACKTEST_CONFIG
    from app.services.backend_client import backend_client

    merged_config = {**DEFAULT_BACKTEST_CONFIG, **req.config}
    # 校驗回測日期區間
    earliest, latest = await backend_client.get_data_range()
    ok, msg = _validate_backtest_dates(merged_config, earliest, latest)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    state.current_config = merged_config
    return {"status": "updated", "config": state.current_config}


@router.get("/data-range")
async def get_data_range():
    """獲取數據庫中已有數據的日期範圍（最早 + 最新交易日）。

    用於前端回測日期選擇器的範圍限制，確保用戶選擇的日期區間有真實數據。

    Returns:
        dict: 包含 earliestTradeDate 和 latestTradeDate 兩個字段
    """
    from app.services.backend_client import backend_client

    earliest, latest = await backend_client.get_data_range()
    return {
        "earliestTradeDate": earliest,
        "latestTradeDate": latest,
    }


@router.post("/model/check")
async def check_model():
    """手動觸發 LLM 模型可用性檢查。

    Returns:
        dict: 當前選中模型狀態 + 全部模型檢查結果列表
              model: 當前選中的供應商（向後兼容）
              models: 全部供應商的檢查結果
    """
    status = await llm_client.check_models()
    return {
        "provider": status.provider,
        "model_name": status.model_name,
        "available": status.available,
        "last_check": status.last_check,
        "error": status.error,
        "models": llm_client.get_all_model_statuses(),
    }


@router.get("/providers")
async def get_providers():
    """獲取當前可用的 LLM 供應商列表（供前端選擇）。

    Returns:
        dict: 包含 providers 列表、當前每階段的供應商偏好設置、默認路由
    """
    from app.core.config import settings
    from app.core.providers import PROVIDERS, STAGE_DEFAULT_PROVIDERS

    return {
        "providers": llm_client.get_available_providers(),
        "stage_preferences": settings.stage_providers,
        "stage_defaults": STAGE_DEFAULT_PROVIDERS,
        "provider_details": {
            pid: {
                "display_name": info.display_name,
                "model_id": info.model_id,
                "is_free": info.is_free,
                "supports_json_mode": info.supports_json_mode,
                "tags": info.tags,
                "description": info.description,
            }
            for pid, info in PROVIDERS.items()
        },
    }


class SetStageProviderRequest(BaseModel):
    """設置某個 AI 階段的供應商偏好。"""

    stage_name: str = ""
    provider: str = ""

    model_config = {"extra": "allow"}

    def effective_stage_name(self) -> str:
        return self.stage_name


@router.post("/providers/stage")
async def set_stage_provider(req: SetStageProviderRequest):
    """設置某個 AI 階段的供應商偏好。

    Args:
        req: 包含 stage_name 和 provider 的請求體
            provider 可選值: deepseek-pro / deepseek-flash / glm-5.2 / glm-flash /
            qwen / qoder / devin / 空字符串(自動選擇)

    Returns:
        dict: 更新後的全部階段供應商偏好
    """
    from app.core.config import settings
    from app.core.providers import PROVIDERS

    valid_providers = list(PROVIDERS.keys()) + [""]
    if req.provider and req.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"provider 必須是 {', '.join(PROVIDERS.keys())} 或空字符串",
        )
    stage = req.effective_stage_name()
    if not stage:
        raise HTTPException(status_code=400, detail="stage_name 不能為空")
    settings.stage_providers[stage] = req.provider
    return {"status": "updated", "stage_preferences": settings.stage_providers}


@router.post("/providers/stage/reset")
async def reset_stage_providers():
    """重置所有階段的供應商偏好為自動選擇。"""
    from app.core.config import settings

    settings.stage_providers = {}
    return {"status": "reset", "stage_preferences": settings.stage_providers}


# ===== 監控端點 =====


@router.get("/monitor")
async def get_monitor_status():
    """獲取監控狀態（節點事件 + 告警 + 統計）。

    Returns:
        dict: 監控器狀態摘要，含事件列表、告警列表和節點統計
    """
    from app.agents.monitor import node_monitor

    return node_monitor.get_status()


@router.get("/monitor/events")
async def get_all_events(limit: int = 500):
    """獲取全部節點事件（用於時間軸可視化）。

    Args:
        limit: 最多返回的事件數（默認 500）

    Returns:
        dict: 全部節點事件列表
    """
    from app.agents.monitor import node_monitor

    return {"events": node_monitor.get_all_events(limit), "total": len(node_monitor._events)}


@router.get("/monitor/timeline")
async def get_timeline():
    """獲取結構化時間軸數據（按迭代分組，用於 Gantt 圖可視化）。

    Returns:
        dict: 按迭代分組的節點執行時間軸 + 節點定義
    """
    from app.agents.monitor import node_monitor

    return node_monitor.get_timeline()


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
