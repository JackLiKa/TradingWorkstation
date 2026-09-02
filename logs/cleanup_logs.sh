#!/bin/bash
#==============================================================================
# Trading Workstation — 日志清理脚本
# 由 crontab 定时调用：0 3 * * 6（每周六凌晨）
# 功能：清理超过 30 天的日志文件
#==============================================================================
set -euo pipefail

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] ===== 开始清理日志 ====="

# 清理 30 天前的日志文件
find "$LOG_DIR" -name '*.log' -type f -mtime +30 -delete 2>/dev/null || true

# 统计剩余日志文件数量
LOG_COUNT=$(find "$LOG_DIR" -name '*.log' -type f 2>/dev/null | wc -l)
LOG_SIZE=$(du -sh "$LOG_DIR" 2>/dev/null | awk '{print $1}')

echo "[$TIMESTAMP] 日志清理完成，剩余 $LOG_COUNT 个日志文件，占用 $LOG_SIZE"
