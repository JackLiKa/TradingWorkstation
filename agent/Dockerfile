# Agent 服務 Dockerfile — 多階段構建優化版
# 構建: docker build -t tw-agent -f agent/Dockerfile .
# build context 為項目根目錄（需要 a-share-mcp 源碼）
# 運行: 由 docker-compose 編排
#
# 優化點:
#   1. 多階段構建，運行時鏡像不含編譯工具
#   2. CPU-only PyTorch，大幅減小體積
#   3. 模型緩存外掛到數據卷，不打包進鏡像

# ===== Stage 1: Builder =====
FROM python:3.12-slim AS builder

WORKDIR /app

# 編譯依編譯依賴（僅 builder 階段，不會進入最終鏡像）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安裝 uv（a-share-mcp 依賴管理）
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# 先安裝 CPU-only PyTorch（避免 sentence-transformers 拉取 GPU 版本）
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 安裝 Agent 服務依賴
COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 a-share-mcp 子服務依賴
COPY a-share-mcp /opt/a-share-mcp
RUN cd /opt/a-share-mcp && uv sync --no-dev

# ===== Stage 2: Runtime =====
FROM python:3.12-slim

WORKDIR /app

# 運行時只需 curl（健康檢查用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 從 builder 複製 Python 依賴（已編譯好的 site-packages）
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 從 builder 複製 uv 和 a-share-mcp
COPY --from=builder /root/.local/bin/uv /root/.local/bin/uv
COPY --from=builder /opt/a-share-mcp /opt/a-share-mcp

# Agent 源碼
COPY agent/app ./app

# 創建數據和日誌目錄
RUN mkdir -p /app/data /app/logs

# 環境變量
ENV LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    ASHARE_MCP_DIR=/opt/a-share-mcp \
    A_SHARE_MCP_PORT=8101 \
    TRANSFORMERS_CACHE=/app/data/model_cache

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:8100/api/agent/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
