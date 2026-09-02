#!/bin/bash
#==============================================================================
# Trading Workstation — 每日数据同步脚本
# 由 crontab 定时调用：0 18 * * 1-5
# 功能：
#   1. 增量更新全部股票日线数据（3 种复权 + 沪深指数）
#   2. 日线更新完成后预计算行情分析快照（market_analysis_snapshot）
#   3. 每周一：额外更新行业分类数据（stock_industry）
#==============================================================================
set -euo pipefail

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 加载 .env 环境变量
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# 宿主机定时任务覆盖：MySQL 容器映射到 localhost:3306
export DB_HOST=localhost

# 日志目录
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DOW=$(date +%u)  # 1=Monday, 7=Sunday

echo "[$TIMESTAMP] ===== 开始每日数据同步 ====="

# Step 1: 增量更新全部股票日线数据（3 种复权 + 沪深指数）
echo "[$TIMESTAMP] Step 1: 增量更新股票日线数据"
python3 ingestion/baostock_ingest.py \
    --mode incremental \
    --adjustflags 1,2,3 \
    --index

echo "[$TIMESTAMP] ===== 日线数据同步完成 ====="

# Step 2: 预计算行情分析快照（每个交易日执行）
echo "[$TIMESTAMP] Step 2: 预计算行情分析快照"
python3 ingestion/precompute_market_snapshot.py --auto 2>&1 || \
    echo "[$TIMESTAMP] ⚠️ 预计算行情快照失败（不阻塞主流程）"

echo "[$TIMESTAMP] ===== 行情分析快照预计算完成 ====="

# Step 3: 每周一额外更新行业分类数据
if [ "$DOW" = "1" ]; then
    echo "[$TIMESTAMP] Step 3: 周一 — 更新行业分类数据"
    python3 ingestion/baostock_ingest.py \
        --mode incremental \
        --adjustflag 3 \
        --sync-industry 2>&1 || \
        echo "[$TIMESTAMP] ⚠️ 行业分类更新失败（不阻塞主流程）"
    echo "[$TIMESTAMP] ===== 行业分类数据更新完成 ====="
fi

echo "[$TIMESTAMP] ===== 每日数据同步全部完成 ====="