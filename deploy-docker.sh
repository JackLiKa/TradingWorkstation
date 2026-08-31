#!/bin/bash
#==============================================================================
# Trading Workstation — 云服务器 Docker 部署脚本
#
# 在云服务器上运行，加载镜像 tar 包并启动全部服务。
#
# 用法:
#   sudo bash deploy-docker.sh <images-tar.gz> [version]
#   sudo bash deploy-docker.sh /tmp/tw-images-abc123.tar.gz abc123
#   sudo bash deploy-docker.sh  # 不传参数，使用 latest 标签
#
# 前置条件:
#   - Docker + Docker Compose 已安装
#   - .env 文件已配置（DB_PASSWORD / API_KEY / LLM keys 等）
#==============================================================================
set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN:${NC} $1"; }
err()  { echo -e "${RED}[$(date +%H:%M:%S)] ERROR:${NC} $1"; }

#==============================================================================
# Step 0: 检查环境
#==============================================================================
log "===== Step 0: 检查服务器环境 ====="

if [[ $EUID -ne 0 ]]; then
   err "此脚本需要 root 权限，请用 sudo 运行"
   exit 1
fi

# 检查 Docker
if ! docker info >/dev/null 2>&1; then
    err "Docker 未安装或未运行"
    log "安装 Docker: curl -fsSL https://get.docker.com | sh"
    log "安装 Compose: apt-get install -y docker-compose-plugin"
    exit 1
fi

# 检查 Docker Compose
if ! docker compose version >/dev/null 2>&1; then
    if ! docker-compose version >/dev/null 2>&1; then
        err "Docker Compose 未安装"
        log "安装: apt-get install -y docker-compose-plugin"
        exit 1
    fi
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi
log "Docker Compose: $COMPOSE_CMD"

TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
TOTAL_DISK=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')
log "服务器配置: ${TOTAL_MEM}GB 内存, ${TOTAL_DISK}GB 可用磁盘"

#==============================================================================
# Step 1: 部署目录 + 配置文件
#==============================================================================
DEPLOY_DIR="/opt/Trading-Workstation"
log "===== Step 1: 部署目录 + 配置 ====="

mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

# 拉取项目代码（docker-compose.yml + docker/init.sql + .env.example）
if [ ! -d ".git" ]; then
    log "克隆项目仓库..."
    git clone https://github.com/JackLiKa/TradingWorkstation.git .
else
    log "更新项目仓库..."
    git pull --ff-only origin main || warn "git pull 失败，使用现有代码继续"
fi

# 配置 .env
if [ ! -f ".env" ]; then
    log "首次部署，从 .env.example 创建 .env"
    cp .env.example .env

    # 生成随机密码（仅首次）
    DB_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
    API_KEY_VAL=$(openssl rand -hex 32)
    GRAFANA_PASS=$(openssl rand -hex 16)

    sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=${DB_PASS}/" .env
    sed -i "s/^API_KEY=.*/API_KEY=${API_KEY_VAL}/" .env
    sed -i "s/^GRAFANA_PASSWORD=.*/GRAFANA_PASSWORD=${GRAFANA_PASS}/" .env

    log ".env 已生成，密码已自动设置"
    log "⚠️  请手动编辑 .env 填入 LLM API Keys（DEEPSEEK/GLM/QWEN 等）"
    warn "部署完成后请记录 .env 中的密码，后续重跑不会重新生成"
else
    log ".env 已存在，复用现有配置"
fi

# 验证必需的环境变量
source .env
if [ -z "$DB_PASSWORD" ]; then
    err "DB_PASSWORD 未设置，请编辑 .env"
    exit 1
fi

#==============================================================================
# Step 2: 加载 Docker 镜像
#==============================================================================
log "===== Step 2: 加载 Docker 镜像 ====="

IMAGES_TAR="${1:-}"
VERSION="${2:-latest}"

if [ -n "$IMAGES_TAR" ] && [ -f "$IMAGES_TAR" ]; then
    log "加载镜像包: $IMAGES_TAR"

    # 解压并加载
    TMP_DIR=$(mktemp -d)
    tar -xzf "$IMAGES_TAR" -C "$TMP_DIR"

    for tar_file in "$TMP_DIR"/*.tar; do
        log "docker load < $tar_file"
        docker load -i "$tar_file"
    done

    rm -rf "$TMP_DIR"
    log "镜像加载完成"
elif [ -n "$IMAGES_TAR" ]; then
    err "镜像包不存在: $IMAGES_TAR"
    exit 1
else
    log "未指定镜像包，使用已存在的 tw-*:latest 镜像"
fi

# 显示当前镜像
log "当前镜像列表："
docker images | grep "tw-" || warn "未找到 tw-* 镜像"

#==============================================================================
# Step 3: 创建 Swap（4GB 服务器推荐）
#==============================================================================
log "===== Step 3: 系统优化 ====="

# 时区
timedatectl set-timezone Asia/Shanghai 2>/dev/null || warn "时区设置失败（不影响部署）"

# Swap
if ! swapon --show | grep -q swapfile; then
    TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$TOTAL_MEM" -le 4 ]; then
        log "创建 2GB Swap（内存 ≤4GB）..."
        fallocate -l 2G /swapfile
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        # 持久化
        if ! grep -q swapfile /etc/fstab; then
            echo '/swapfile none swap sw 0 0' >> /etc/fstab
        fi
        log "Swap 已创建"
    fi
else
    log "Swap 已存在，跳过"
fi

#==============================================================================
# Step 4: 防火墙
#==============================================================================
log "===== Step 4: 防火墙配置 ====="

if command -v ufw >/dev/null 2>&1; then
    ufw allow 22/tcp    >/dev/null 2>&1 || true  # SSH
    ufw allow 80/tcp    >/dev/null 2>&1 || true  # HTTP（Nginx 反代）
    ufw allow 443/tcp   >/dev/null 2>&1 || true  # HTTPS
    # 内部端口不对外暴露（3010/8090/8100 由 Nginx 反代或仅本地访问）
    ufw --force enable >/dev/null 2>&1 || true
    log "UFW 防火墙已配置（仅开放 22/80/443）"
else
    warn "UFW 未安装，跳过防火墙配置"
fi

#==============================================================================
# Step 5: 启动服务
#==============================================================================
log "===== Step 5: 启动 Docker 服务 ====="

# 停止旧容器（如果有）
$COMPOSE_CMD down --remove-orphans 2>/dev/null || true

# 启动全部服务
$COMPOSE_CMD up -d

log "等待服务启动..."
sleep 10

#==============================================================================
# Step 6: 健康检查
#==============================================================================
log "===== Step 6: 健康检查 ====="

check_service() {
    local name=$1
    local url=$2
    local max_retries=$3
    local retry=0

    while [ $retry -lt $max_retries ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            log "✓ $name 健康 ($url)"
            return 0
        fi
        retry=$((retry + 1))
        sleep 5
    done

    warn "✗ $name 未就绪 ($url) — 请检查日志: $COMPOSE_CMD logs $name"
    return 1
}

# MySQL
check_service "MySQL" "http://localhost:3306" 3 || true

# Java 后端
check_service "Java 后端" "http://localhost:8090/TradingWorkstation/actuator/health" 10 || true

# Next.js 前端
check_service "Next.js 前端" "http://localhost:3010/TradingWorkstation" 6 || true

# Agent 服务
check_service "Agent 服务" "http://localhost:8100/api/agent/health" 10 || true

#==============================================================================
# Step 7: 状态汇总
#==============================================================================
log ""
log "===== 部署完成 ====="
log ""
log "服务状态："
$COMPOSE_CMD ps
log ""
log "端口映射："
log "  MySQL:          localhost:3306"
log "  Java 后端:      localhost:8090/TradingWorkstation"
log "  Next.js 前端:   localhost:3010/TradingWorkstation"
log "  Agent 服务:     localhost:8100/api/agent"
log "  Prometheus:     localhost:9090（可选）"
log "  Grafana:        localhost:3000（可选）"
log ""
log "常用命令："
log "  查看日志:   $COMPOSE_CMD logs -f <service>"
log "  重启服务:   $COMPOSE_CMD restart <service>"
log "  停止全部:   $COMPOSE_CMD down"
log "  查看状态:   $COMPOSE_CMD ps"
log ""
log "⚠️  数据采集：MySQL 容器已启动，需在宿主机配置 cron 定时运行 ingestion 脚本"
log "    示例 crontab: 0 16 * * 1-5 cd $DEPLOY_DIR && python ingestion/baostock_ingest.py --mode incremental --adjustflags 1,2,3 --index"
log ""
log "⚠️  如需 Nginx 反代（80/443 → 3010），请参考 docs/DEPLOYMENT.md"
