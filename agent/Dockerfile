# Agent 服務 Dockerfile — 自包含（含 a-share-mcp 子服務）
# 構建: docker build -t tw-agent -f agent/Dockerfile .
# build context 為項目根目錄（需要 a-share-mcp 源碼）
# 運行: 由 docker-compose 編排
#
# 鏡像包含：
#   1. Agent 服務本身（FastAPI + LLM 路由 + 新聞同步）
#   2. a-share-mcp 子服務（Baostock MCP，Agent 啟動時自動拉起）
#   3. uv（a-share-mcp 的依賴管理工具）
#   4. Milvus Lite（嵌入式向量庫，無需獨立容器）

FROM python:3.12-slim

WORKDIR /app

# ===== 系統依賴 =====
# build-essential: sentence-transformers 編譯需要
# curl: 健康檢查
# git: uv 安裝需要
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# ===== 安裝 uv（a-share-mcp 依賴管理）=====
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# ===== Agent 服務依賴 =====
# build context 是項目根目錄，所以路徑帶 agent/ 前綴
COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ===== a-share-mcp 子服務 =====
# 複製 a-share-mcp 源碼到 /opt/a-share-mcp（排除 .venv 由 .dockerignore 控制）
COPY a-share-mcp /opt/a-share-mcp

# 安裝 a-share-mcp 依賴（uv sync 創建 .venv）
RUN cd /opt/a-share-mcp && uv sync --no-dev

# ===== Agent 源碼 =====
COPY agent/app ./app

# 創建數據和日誌目錄（Milvus Lite + Agent 狀態 + 日誌）
RUN mkdir -p /app/data /app/logs

# ===== 環境變量 =====
ENV LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    # a-share-mcp 目錄覆蓋（Docker 內路徑）
    ASHARE_MCP_DIR=/opt/a-share-mcp \
    # a-share-mcp 端口（容器內部，無需暴露）
    A_SHARE_MCP_PORT=8101

# 暴露 Agent 服務端口
EXPOSE 8100

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:8100/api/agent/health || exit 1

# 啟動命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
