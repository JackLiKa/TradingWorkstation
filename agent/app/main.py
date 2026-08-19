"""Agent 服務入口 — FastAPI 應用。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.services.model_checker import model_checker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期管理：啟動時初始化日誌與定時任務，關閉時清理資源。

    Args:
        app: FastAPI 應用實例（由框架自動注入）
    """
    setup_logging()
    logger.info("Agent 服務啟動中...")

    # 啟動模型檢查定時任務
    model_checker.start()

    logger.info(f"Agent 服務已啟動，端口 {settings.agent_port}")
    yield

    # 關閉清理
    await model_checker.stop()
    # 關閉後端連接池
    from app.services.backend_client import backend_client
    await backend_client.aclose()
    logger.info("Agent 服務已關閉")


app = FastAPI(
    title="量化交易 AI 優化 Agent",
    description="自動優化回測策略的 AI Agent 服務",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — 允許前端跨域訪問（Next.js 默認 3010，備用 3000）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3010", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由 — 所有接口統一掛載在 /api/agent 前綴下
app.include_router(router, prefix="/api/agent", tags=["agent"])


@app.get("/")
async def root():
    """根路徑健康探針，返回服務名稱、版本及文檔路徑。

    Returns:
        dict: 包含 service / version / docs 三個字段的服務基本信息
    """
    return {"service": "quantization-agent", "version": "1.0.0", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.agent_port,
        reload=True,
    )
