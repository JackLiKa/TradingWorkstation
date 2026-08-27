"""API Key 認證中間件 — 保護 Agent 服務端點。

啟用條件：settings.api_key 非空。
開發環境默認關閉（api_key 為空時跳過認證）。
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings

logger = logging.getLogger("agent.auth")


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """檢查 X-API-Key 請求頭，未通過則返回 401。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # 開發環境無 api_key 時跳過認證
        if not settings.api_key:
            return await call_next(request)

        # 健康檢查端點不需要認證
        path = request.url.path
        if path.endswith("/health") or path.endswith("/metrics") or path.endswith("/docs") or path.endswith("/openapi.json"):
            return await call_next(request)

        provided = request.headers.get("X-API-Key")
        if provided != settings.api_key:
            logger.warning(f"未授權請求: {path} (來源: {request.client.host if request.client else 'unknown'})")
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized: missing or invalid API key"},
            )

        return await call_next(request)
