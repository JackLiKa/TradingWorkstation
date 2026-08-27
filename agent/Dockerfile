# Agent 服務 Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 系統依賴（sentence-transformers 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 先複製 requirements（利用 Docker 層緩存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製源碼
COPY . .

# 創建數據和日誌目錄
RUN mkdir -p /app/data /app/logs

# 環境變量默認值
ENV LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 8100

# 健康檢查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8100/api/agent/health', timeout=3)" || exit 1

# 啟動命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
