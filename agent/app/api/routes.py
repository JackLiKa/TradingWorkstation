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


@router.get("/monitor/errors")
async def get_error_experiences(limit: int = 100):
    """獲取錯誤/重試經驗記錄（持久化存儲，供後續優化復用）。

    Args:
        limit: 最多返回的記錄數（默認 100）

    Returns:
        dict: 錯誤記錄列表 + 統計摘要
    """
    from app.services import error_store

    return {
        "errors": error_store.get_all_errors(limit),
        "stats": error_store.get_error_stats(),
    }


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


@router.get("/news/search")
async def search_news(keyword: str, page_size: int = 10):
    """按關鍵詞搜索財經新聞 — 供前端行業走勢圖疊加新聞標記使用。

    Args:
        keyword: 搜索關鍵詞（如行業名稱「半導體」「新能源」）
        page_size: 返回新聞條數（默認 10，最大 30）

    Returns:
        dict: 包含 keyword 和 news 列表（每項含 title/source/date/url）
    """
    page_size = max(1, min(page_size, 30))
    from app.services.market_data_client import market_data_client

    news = await market_data_client.search_news_by_keyword(keyword, page_size=page_size)
    return {"keyword": keyword, "news": news}


@router.post("/news/sync")
async def sync_wallstreetcn_news(channel: str = "a-stock", limit: int = 50):
    """觸發華爾街見聞新聞同步 — 抓取最新新聞並存入向量庫 + MySQL。

    Args:
        channel: 頻道（global/a-stock/us-stock/hk-stock/forex/commodity/all）
                 all = 全量同步所有頻道 + 頭條 + 熱文 + 快訊
        limit: 抓取條數（默認 50，最大 200；channel=all 時忽略）
    """
    limit = max(1, min(limit, 200))
    from app.services import news_store

    result = await news_store.sync_news_to_vector_store(channel=channel, limit=limit)
    return {
        "status": "SUCCESS",
        "channel": channel,
        "fetched": result["fetched"],
        "stored": result["stored"],
        "duplicated": result["duplicated"],
        "failed": result["failed"],
        "mysql_stored": result.get("mysql_stored", 0),
        "mysql_duplicated": result.get("mysql_duplicated", 0),
    }


@router.get("/news/wallstreetcn/search")
async def search_wallstreetcn(keyword: str, limit: int = 10):
    """從華爾街見聞搜索新聞（實時抓取，不入庫）。"""
    limit = max(1, min(limit, 20))
    from app.services import wallstreetcn_client

    news = await wallstreetcn_client.search_articles(keyword, limit=limit)
    return {"keyword": keyword, "news": news, "source": "華爾街見聞"}


@router.get("/news/wallstreetcn/latest")
async def get_wallstreetcn_latest(channel: str = "a-stock", limit: int = 50):
    """從華爾街見聞抓取最新新聞（實時抓取，不入庫）。

    Args:
        channel: 頻道（global/a-stock/us-stock/hk-stock/forex/commodity/all）
        limit: 返回條數上限（最大 200）
    """
    limit = max(1, min(limit, 200))
    from app.services import wallstreetcn_client

    if channel == "all":
        news = await wallstreetcn_client.fetch_all_channels(limit_per_channel=max(limit // 6, 30))
    elif channel == "a-stock":
        news = await wallstreetcn_client.fetch_a_stock_focused(limit=limit)
    else:
        news = await wallstreetcn_client.fetch_latest_articles(channel, limit=limit)
    return {"channel": channel, "news": news, "source": "華爾街見聞"}


@router.get("/news/vector/search")
async def vector_search_news(
    query: str,
    top_k: int = 10,
    channel: str | None = None,
    days_back: int = 7,
):
    """從向量庫語義檢索新聞（需 Milvus + embedding 可用）。"""
    from app.services import news_store

    if not news_store.is_available():
        raise HTTPException(status_code=503, detail="新聞向量庫不可用（Milvus 或 embedding 未初始化）")

    news = news_store.search_relevant_news(
        query=query, top_k=top_k, channel=channel, days_back=days_back
    )
    return {"query": query, "news": news, "count": len(news)}


@router.get("/news/vector/search_rerank")
async def vector_search_news_with_rerank(
    query: str,
    top_k: int = 10,
    channel: str | None = None,
    days_back: int = 7,
    candidate_multiplier: int = 3,
    preferred_provider: str = "",
):
    """向量搜索 TopK 初篩 + LLM 重排序。

    解決純向量搜索對「利好/利空」等情感方向詞區分能力弱的問題：
    1. 向量搜索取 top_k * candidate_multiplier 條候選
    2. LLM 根據查詢意圖（含情感方向）對候選逐條打分
    3. 按分數排序返回 top_k 條

    Args:
        query: 查詢文本（如「半導體行業利好」「A股市場利空」）
        top_k: 最終返回條數
        channel: 頻道過濾
        days_back: 時間過濾
        candidate_multiplier: 初篩倍數（候選數 = top_k * multiplier）
        preferred_provider: 首選 LLM 供應商（如 glm-flash/deepseek-flash）
    """
    from app.services import news_store
    from app.services.news_reranker import search_with_rerank

    if not news_store.is_available():
        raise HTTPException(status_code=503, detail="新聞向量庫不可用（Milvus 或 embedding 未初始化）")

    news = await search_with_rerank(
        query=query,
        top_k=top_k,
        channel=channel,
        days_back=days_back,
        candidate_multiplier=candidate_multiplier,
        preferred_provider=preferred_provider,
    )
    return {
        "query": query,
        "news": news,
        "count": len(news),
        "reranked": True,
    }


@router.get("/news/vector/status")
async def get_news_vector_status():
    """獲取新聞向量庫狀態。"""
    from app.services import news_store

    return news_store.get_status()


@router.get("/news/throttle/status")
async def get_news_throttle_status():
    """獲取華爾街見聞 API 請求節流狀態。

    返回上次請求時間、最小間隔、下次可請求時間、緩存條目數。
    """
    from app.services.wallstreetcn_client import _throttle

    return _throttle.get_status()


@router.get("/news/sync/status")
async def get_news_sync_status():
    """獲取新聞自動同步狀態。

    返回同步排程器狀態：是否啟用、同步間隔、補抓狀態、最近同步結果。
    """
    from app.core.config import settings
    from app.services.news_sync_scheduler import news_sync_scheduler

    return {
        "enabled": settings.news_sync_enabled,
        "interval_seconds": settings.news_sync_interval,
        "catchup_days": settings.news_sync_catchup_days,
        "channels": settings.news_sync_channels,
        "catchup_done": news_sync_scheduler.catchup_done,
        "last_catchup_result": news_sync_scheduler.last_catchup_result,
        "last_sync_result": news_sync_scheduler.last_sync_result,
    }


@router.post("/news/sync/catchup")
async def trigger_news_catchup(days: int = 7):
    """手動觸發新聞補抓（追回指定天數的歷史新聞）。"""
    from app.services import news_store

    result = await news_store.catchup_news(
        channels=None,  # 全頻道
        catchup_days=days,
    )
    return {"status": "SUCCESS", "result": result}


@router.post("/news/cleanup")
async def cleanup_expired_news():
    """清理過期新聞（從向量庫刪除超過 TTL 的記錄）。"""
    from app.services import news_store

    deleted = news_store.cleanup_expired_news()
    return {"deleted": deleted, "status": "SUCCESS"}


@router.post("/news/dedup")
async def dedup_vector_store():
    """清理向量庫中的重複新聞（保留每個 URI 的第一條）。"""
    from app.services import news_store

    result = news_store.dedup_vector_store()
    return {"status": "SUCCESS", **result}


@router.post("/news/rebuild")
async def rebuild_vector_store():
    """重建向量庫 collection — 刪除所有歷史數據並重新創建。

    用於清理錯誤 URL 等歷史髒數據。重建後需重新同步新聞。
    """
    from app.services import news_store

    success = news_store.rebuild_collection()
    return {"status": "SUCCESS" if success else "FAILED", "rebuilt": success}


# ===== AI 聊天（悬浮卡片）=====


class ChatStreamRequest(BaseModel):
    """聊天流式請求 — 用戶發送消息並獲取 SSE 流式回復。

    安全限制：
    - messages 最多 50 條（防止 token 耗盡攻擊）
    - 每條消息 content 最多 10000 字符
    - provider 限制長度（防止注入）
    """
    from pydantic import Field

    messages: list[dict[str, Any]] = Field(
        ..., max_length=50, description="對話歷史，最多 50 條消息"
    )
    provider: str = Field(default="", max_length=50, description="LLM 供應商 ID")


@router.get("/chat/providers")
async def get_chat_providers():
    """獲取可用於聊天的 LLM 供應商列表。

    包含所有供應商（不僅限 function calling），因為：
    - 工具調用階段自動用 deepseek-flash
    - 最終總結階段用用戶選擇的供應商（通過 llm_client 降級鏈）
    """
    from app.chat.engine import CHAT_PROVIDERS
    from app.core.providers import PROVIDERS, get_api_key

    providers = []
    for pid in CHAT_PROVIDERS:
        if pid in PROVIDERS:
            info = PROVIDERS[pid]
            providers.append({
                "provider": pid,
                "display_name": info.display_name,
                "model_id": info.model_id,
                "is_free": info.is_free,
                "available": bool(get_api_key(pid)),
                "description": info.description,
            })
    return {"providers": providers}


@router.get("/chat/tools")
async def get_chat_tools():
    """獲取可用工具列表（供前端展示工具能力）。"""
    from app.chat.registry import init_tools, registry

    init_tools()
    tools = []
    for tool in registry.all_tools():
        tools.append({
            "name": tool.name,
            "display_name": tool.display_name,
            "description": tool.description,
        })
    return {"tools": tools}


@router.post("/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    """SSE 流式聊天端點 — 返回 Server-Sent Events 流。

    流式協議（每行一個 JSON 事件）：
    - {"type":"tool_start","tool":"open_web_search","arguments":{...}}
    - {"type":"tool_end","tool":"open_web_search","success":true,"citations":[...]}
    - {"type":"content","text":"..."}  — 文本塊
    - {"type":"done","provider":"...","model":"...","citations":[...],"tool_calls_log":[...]}
    - {"type":"error","message":"..."}
    """
    import json

    from fastapi.responses import StreamingResponse

    from app.chat.engine import ChatMessage, chat_engine

    # 構建聊天消息列表
    messages = [
        ChatMessage(role=m.get("role", "user"), content=m.get("content", ""))
        for m in request.messages
    ]

    async def event_generator():
        """SSE 事件生成器。"""
        try:
            async for chunk in chat_engine.chat_stream(messages, request.provider):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            error_msg = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 緩衝
        },
    )


# ===== 回顧分析 AI（每5輪分析各AI輸入輸出）=====


@router.post("/retrospective/trigger")
async def trigger_retrospective(window_size: int = 5):
    """手動觸發回顧分析 — 分析最近 N 輪各AI節點的輸入輸出。

    Args:
        window_size: 回顧窗口大小（默認5輪）
    """
    from app.agents.optimizer import state
    from app.agents.stages.retrospective import run_retrospective

    if len(state.iterations) < window_size:
        return {
            "status": "FAILED",
            "message": f"迭代數不足（當前 {len(state.iterations)} 輪，需要至少 {window_size} 輪）",
        }

    result = await run_retrospective(state, window_size=window_size)
    if result:
        return {"status": "SUCCESS", "result": result.to_dict()}
    return {"status": "FAILED", "message": "回顧分析失敗（查看日誌）"}


@router.get("/retrospective/latest")
async def get_latest_retrospective():
    """獲取最近一次回顧分析結果。"""
    from app.agents.optimizer import state

    if state.last_retrospective:
        return {"status": "SUCCESS", "result": state.last_retrospective.to_dict()}
    return {"status": "SUCCESS", "result": None}


# ===== 當日市場摘要 AI（按需生成 + 同日複用）=====


@router.post("/daily-digest/generate")
async def generate_daily_digest(force: bool = False):
    """按需生成當日市場摘要 — 從DB+工具+MCP獲取數據，凝練濃縮後持久化。

    Args:
        force: 是否強制重新生成（即使當日已有摘要）

    Returns:
        status=SUCCESS + result: 摘要內容
        status=FAILED + message: 失敗原因（無數據/LLM失敗/後端不可用等）
    """
    from app.services.daily_digest import generate_digest

    result = await generate_digest(force=force)
    if result:
        return {"status": "SUCCESS", "result": result.to_dict()}
    return {
        "status": "FAILED",
        "message": "摘要生成失敗：可能原因為該交易日無市場數據、LLM返回空內容或後端不可用。請查看 Agent 日誌確認具體原因。",
    }


@router.get("/daily-digest/{trade_date}")
async def get_daily_digest(trade_date: str):
    """按交易日查詢當日市場摘要。

    返回標準化 snake_case 格式（兼容 Java camelCase API 響應）。
    """
    from app.agents.state import DailyDigest
    from app.services.backend_client import backend_client

    data = await backend_client.load_daily_digest(trade_date)
    if not data:
        return {"status": "SUCCESS", "data": None}
    # 用 from_dict 兼容 camelCase → to_dict 輸出標準 snake_case
    digest = DailyDigest.from_dict(data)
    if digest.is_empty():
        return {"status": "SUCCESS", "data": None}
    return {"status": "SUCCESS", "data": digest.to_dict()}


@router.get("/daily-digest/latest")
async def get_latest_daily_digest():
    """獲取最新的當日市場摘要。

    返回標準化 snake_case 格式（兼容 Java camelCase API 響應）。
    """
    from app.agents.state import DailyDigest
    from app.services.backend_client import backend_client

    data = await backend_client.load_latest_daily_digest()
    if not data:
        return {"status": "SUCCESS", "data": None}
    digest = DailyDigest.from_dict(data)
    if digest.is_empty():
        return {"status": "SUCCESS", "data": None}
    return {"status": "SUCCESS", "data": digest.to_dict()}


# ===== 數據質量檢查 =====


@router.post("/data-quality/run")
async def run_data_quality_checks():
    """執行數據質量 SQL 規則檢查。

    純 SQL 規則集，零 AI 幻覺風險。返回結構化報告。
    """
    from app.services.data_quality import run_quality_checks

    report = run_quality_checks()
    return {"status": "SUCCESS", "data": report}


@router.post("/data-quality/run-with-ai-summary")
async def run_data_quality_with_ai():
    """執行數據質量檢查 + AI 生成自然語言總結報告。

    SQL 規則做檢測（100% 準確），免費 LLM 做總結（glm-flash）。
    """
    from app.services.data_quality import run_quality_checks, generate_ai_summary

    report = run_quality_checks()
    ai_summary = await generate_ai_summary(report)
    report["ai_summary"] = ai_summary
    return {"status": "SUCCESS", "data": report}


@router.get("/data-quality/rules")
async def list_quality_rules():
    """列出所有數據質量規則（不執行，僅展示規則定義）。"""
    from app.services.data_quality import QUALITY_RULES

    rules = [
        {
            "rule_id": r[0],
            "severity": r[1],
            "description": r[2],
            "expected_zero": r[4],
        }
        for r in QUALITY_RULES
    ]
    return {"status": "SUCCESS", "data": rules}


# ===== 日誌查看（供前端日誌頁面聚合）=====


@router.get("/logs/recent")
async def get_recent_logs(limit: int = 100):
    """獲取最近的 Agent 服務日誌（從 agent.log 文件讀取最後 N 行）。

    Args:
        limit: 返回的最大行數（默認 100）

    Returns:
        dict: 日誌條目列表，每條包含 timestamp/level/logger/message/raw
    """
    import re
    from pathlib import Path

    log_file = Path(__file__).resolve().parent.parent.parent / "logs" / "agent.log"
    if not log_file.exists():
        return {"entries": [], "file": str(log_file), "exists": False}

    # 讀取最後 N 行
    lines = _tail_file(log_file, limit)

    # 解析日誌行：格式 "2026-08-29 02:30:16 [INFO] agent.api: message"
    pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] ([^:]+): (.*)$"
    )

    entries = []
    for i, line in enumerate(lines):
        line = line.rstrip("\n\r")
        m = pattern.match(line)
        if m:
            entries.append({
                "id": f"agent:{i}",
                "source": "agent",
                "timestamp": m.group(1),
                "level": m.group(2),
                "logger": m.group(3).strip(),
                "message": m.group(4),
                "raw": line,
            })
        else:
            # 無法解析的行（可能是多行堆棧跟蹤的續行）
            if entries:
                entries[-1]["raw"] += "\n" + line
            else:
                entries.append({
                    "id": f"agent:{i}",
                    "source": "agent",
                    "timestamp": "",
                    "level": "INFO",
                    "logger": "",
                    "message": line,
                    "raw": line,
                })

    # 倒序（最新的在前）
    entries.reverse()
    return {"entries": entries, "file": str(log_file), "exists": True}


@router.get("/logs/stream")
async def stream_logs():
    """SSE 實時推送 Agent 日誌新行。

    每 2 秒檢查一次 agent.log 文件是否有新增行，有則推送。
    """
    import asyncio
    import json
    import re
    from pathlib import Path

    from fastapi.responses import StreamingResponse

    log_file = Path(__file__).resolve().parent.parent.parent / "logs" / "agent.log"
    pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] ([^:]+): (.*)$"
    )

    async def event_generator():
        """SSE 事件生成器 — 輪詢日誌文件新增行。"""
        last_pos = 0
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, 2)  # 跳到文件末尾
                last_pos = f.tell()

        while True:
            try:
                if not log_file.exists():
                    await asyncio.sleep(2)
                    continue

                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    last_pos = f.tell()

                for line in new_lines:
                    line = line.rstrip("\n\r")
                    if not line:
                        continue
                    m = pattern.match(line)
                    if m:
                        entry = {
                            "id": f"agent:{last_pos}",
                            "source": "agent",
                            "timestamp": m.group(1),
                            "level": m.group(2),
                            "logger": m.group(3).strip(),
                            "message": m.group(4),
                            "raw": line,
                        }
                    else:
                        entry = {
                            "id": f"agent:{last_pos}",
                            "source": "agent",
                            "timestamp": "",
                            "level": "INFO",
                            "logger": "",
                            "message": line,
                            "raw": line,
                        }
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"

                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _tail_file(path: "Path", n: int) -> list[str]:
    """高效讀取文件最後 N 行。"""
    try:
        with open(path, "rb") as f:
            # 從文件末尾向前讀
            f.seek(0, 2)
            file_size = f.tell()
            block_size = 1024
            blocks = []
            pos = file_size
            while pos > 0 and sum(len(b) for b in blocks) < n * 200:
                read_size = min(block_size, pos)
                pos -= read_size
                f.seek(pos)
                blocks.insert(0, f.read(read_size))
            all_text = b"".join(blocks).decode("utf-8", errors="replace")
            lines = all_text.splitlines()
            return lines[-n:] if len(lines) > n else lines
    except Exception:
        return []

