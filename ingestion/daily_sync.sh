#!/bin/bash
# A股交易日18:00自动数据更新脚本
# 判断当天是否为交易日（排除周末和法定节假日）
# 如果是交易日则后台运行 baostock_ingest.py 增量更新全部数据

set -e

PROJECT_DIR="/home/ubuntu/TradingWorkstation"
INGESTION_DIR="$PROJECT_DIR/ingestion"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/daily_sync_$(date +%Y%m%d).log"
PYTHON_BIN="/usr/bin/python3"
export PYTHONPATH="$HOME/.local/lib/python3.12/site-packages:${PYTHONPATH:-}"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 判断是否为交易日
# 周末（周六=6, 周日=0）直接跳过
DOW=$(date +%u)
if [ "$DOW" -ge 6 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 今天是周末，跳过数据更新" >> "$LOG_FILE"
    exit 0
fi

# 简单的法定节假日判断（可根据需要扩展）
# 元旦、春节、清明、劳动节、端午、中秋、国庆等
# 这里使用日期匹配，实际节假日可能每年不同
TODAY=$(date +%m%d)
HOLIDAYS="0101 0102 0103 0501 1001 1002 1003 1004 1005 1006 1007"
for holiday in $HOLIDAYS; do
    if [ "$TODAY" = "$holiday" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 今天是法定节假日（$TODAY），跳过数据更新" >> "$LOG_FILE"
        exit 0
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行交易日数据更新..." >> "$LOG_FILE"

# 后台运行数据更新脚本（增量模式，三种复权 + 指数 + 行业）
cd "$INGESTION_DIR"
$PYTHON_BIN baostock_ingest.py \
    --mode incremental \
    --adjustflags 1,2,3 \
    --index \
    --industry \
    --progress-json \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 数据更新完成，退出码: $EXIT_CODE" >> "$LOG_FILE"

# 如果更新失败，记录错误信息
if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 数据更新失败，退出码: $EXIT_CODE" >> "$LOG_FILE"
fi

exit $EXIT_CODE
