#!/bin/bash
#==============================================================================
# Trading Workstation — 腾讯云 4核4G 服务器一键部署脚本
# 操作系统: Ubuntu Server 22.04 LTS
# 用法: bash deploy.sh
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
# 配置区 — 按需修改
#==============================================================================
PROJECT_DIR="/opt/Trading-Workstation"
REPO_URL="https://github.com/JackLiKa/TradingWorkstation.git"
DB_NAME="a_stock_baostock"
DB_USER="twuser"
# 生成随机密码（也可以手动指定）
DB_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
API_KEY=$(openssl rand -hex 32)

#==============================================================================
# Step 0: 检查环境
#==============================================================================
log "===== Step 0: 检查服务器环境 ====="

if [[ $EUID -ne 0 ]]; then
   err "此脚本需要 root 权限，请用 sudo 运行"
   exit 1
fi

TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
TOTAL_DISK=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')
log "服务器配置: ${TOTAL_MEM}GB 内存, ${TOTAL_DISK}GB 可用磁盘"

if [[ $TOTAL_MEM -lt 3 ]]; then
    warn "内存 <3GB，建议至少 4GB"
fi

#==============================================================================
# Step 1: 系统基础配置
#==============================================================================
log "===== Step 1: 系统基础配置 ====="

# 时区
timedatectl set-timezone Asia/Shanghai
log "时区已设置: $(timedatectl --get | grep 'Time zone')"

# 创建 Swap（4GB 内存必须加）
if ! swapon --show | grep -q swapfile; then
    log "创建 4GB Swap..."
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    log "Swap 已创建: $(free -h | awk '/Swap/{print $2}')"
else
    log "Swap 已存在，跳过"
fi

# 系统更新
log "更新系统包..."
apt update -qq && apt upgrade -y -qq

# 基础工具
apt install -y -qq curl wget git vim ufw fail2ban htop \
    build-essential pkg-config libssl-dev libffi-dev \
    python3-dev 2>/dev/null

log "Step 1 完成"

#==============================================================================
# Step 2: 安装 MySQL 8.0
#==============================================================================
log "===== Step 2: 安装 MySQL 8.0 ====="

if ! command -v mysql &>/dev/null; then
    log "安装 MySQL Server..."
    apt install -y -qq mysql-server
    
    # 安全初始化（非交互式）
    mysql -u root <<EOF
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '${DB_PASSWORD}';
DELETE FROM mysql.user WHERE User='';
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost','127.0.0.1','::1');
DROP DATABASE IF EXISTS test;
DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
FLUSH PRIVILEGES;
EOF
    
    log "MySQL root 密码已设置"
else
    log "MySQL 已安装，跳过"
fi

# 创建数据库和用户
mysql -u root -p"${DB_PASSWORD}" <<EOF
CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
EOF
log "数据库 ${DB_NAME} 和用户 ${DB_USER} 已创建"

# MySQL 内存调优（4GB 服务器）
log "配置 MySQL 内存限制..."
cat > /etc/mysql/mysql.conf.d/tw-tuning.cnf <<EOF
# Trading Workstation — 4GB 服务器调优
[mysqld]
innodb_buffer_pool_size = 256M
max_connections = 30
key_buffer_size = 32M
table_open_cache = 200
innodb_redo_log_capacity = 256M
innodb_flush_log_at_trx_commit = 2
EOF

systemctl restart mysql
systemctl enable mysql
log "MySQL 已启动并调优"

#==============================================================================
# Step 3: 安装 JDK 21
#==============================================================================
log "===== Step 3: 安装 JDK 21 ====="

if ! java -version 2>&1 | grep -q '21'; then
    log "安装 OpenJDK 21..."
    apt install -y -qq openjdk-21-jdk
else
    log "JDK 21 已安装: $(java -version 2>&1 | head -1)"
fi

# Maven
if ! command -v mvn &>/dev/null; then
    log "安装 Maven..."
    apt install -y -qq maven
fi
log "Java: $(java -version 2>&1 | head -1)"
log "Maven: $(mvn -v 2>&1 | head -1)"

#==============================================================================
# Step 4: 安装 Node.js 20
#==============================================================================
log "===== Step 4: 安装 Node.js 20 ====="

if ! node -v 2>&1 | grep -q 'v20'; then
    log "安装 Node.js 20 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y -qq nodejs
else
    log "Node.js 已安装: $(node -v)"
fi
log "Node: $(node -v), npm: $(npm -v)"

#==============================================================================
# Step 5: 安装 Python 3.12 + uv
#==============================================================================
log "===== Step 5: 安装 Python + uv ====="

apt install -y -qq python3 python3-pip python3-venv 2>/dev/null

if ! command -v uv &>/dev/null; then
    log "安装 uv (Python 包管理器)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    # 写入 profile
    grep -q '.local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
fi
log "Python: $(python3 --version)"
log "uv: $(uv --version 2>/dev/null || echo '已安装')"

#==============================================================================
# Step 6: 拉取项目代码
#==============================================================================
log "===== Step 6: 拉取项目代码 ====="

if [[ -d "${PROJECT_DIR}/.git" ]]; then
    log "项目已存在，拉取最新代码..."
    cd "${PROJECT_DIR}"
    git pull
else
    log "克隆项目到 ${PROJECT_DIR}..."
    mkdir -p /opt
    git clone "${REPO_URL}" "${PROJECT_DIR}"
    cd "${PROJECT_DIR}"
fi
log "当前版本: $(git log --oneline -1)"

#==============================================================================
# Step 7: 配置环境变量
#==============================================================================
log "===== Step 7: 配置环境变量 ====="

cd "${PROJECT_DIR}"

# 根 .env
if [[ ! -f .env ]]; then
    cp .env.example .env
fi

# 更新关键配置
update_env() {
    local file=$1 key=$2 value=$3
    if grep -q "^${key}=" "$file"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    else
        echo "${key}=${value}" >> "$file"
    fi
}

update_env .env DB_HOST localhost
update_env .env DB_PORT 3306
update_env .env DB_NAME "${DB_NAME}"
update_env .env DB_USER "${DB_USER}"
update_env .env DB_PASSWORD "${DB_PASSWORD}"
update_env .env DB_CHARSET utf8mb4
update_env .env SERVER_PORT 8090
update_env .env SERVER_CONTEXT_PATH /TradingWorkstation
update_env .env CORS_ALLOWED_ORIGINS "http://localhost:3010,http://127.0.0.1:3010"
update_env .env SECURITY_ENABLED true
update_env .env API_KEY "${API_KEY}"
update_env .env SYNC_DAILY_ENABLED false
update_env .env SYNC_CATCHUP_ON_STARTUP false
update_env .env SYNC_QUARTERLY_REFRESH false

log "根 .env 已配置（DB_PASSWORD 和 API_KEY 已自动生成）"

# Agent .env
cd "${PROJECT_DIR}/agent"
if [[ ! -f .env ]]; then
    cp .env.example .env
fi

update_env .env BACKEND_API_URL "http://localhost:8090/TradingWorkstation"
update_env .env BACKEND_API_KEY "${API_KEY}"
update_env .env API_KEY "${API_KEY}"
update_env .env AGENT_PORT 8100
update_env .env LOG_LEVEL INFO
update_env .env ENVIRONMENT production
update_env .env NEWS_SYNC_ENABLED true
update_env .env NEWS_SYNC_INTERVAL 360
update_env .env NEWS_SYNC_CATCHUP_ON_STARTUP true

log "agent/.env 已配置"

# 显示需要手动填写的密钥
echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}⚠️  需要手动编辑 agent/.env 填入 LLM API Key${NC}"
echo -e "${YELLOW}========================================${NC}"
echo -e "  cd ${PROJECT_DIR}/agent && nano .env"
echo -e "  至少填一个：DEVIN_API_KEY / GLM_API_KEY / DEEPSEEK_API_KEY"
echo ""

#==============================================================================
# Step 8: 构建 Java 后端
#==============================================================================
log "===== Step 8: 构建 Java 后端 ====="

cd "${PROJECT_DIR}/java"
log "Maven 编译（跳过测试）..."
mvn -B -DskipTests package -q
log "Java 后端构建完成: $(ls target/*.jar)"

#==============================================================================
# Step 9: 构建 Next.js 前端
#==============================================================================
log "===== Step 9: 构建 Next.js 前端 ====="

cd "${PROJECT_DIR}/next"
log "安装 npm 依赖..."
npm install --legacy-peer-deps 2>/dev/null || npm install --legacy-peer-deps
log "构建生产版本..."
npm run build
log "Next.js 构建完成"

#==============================================================================
# Step 10: 安装 Agent Python 依赖
#==============================================================================
log "===== Step 10: 安装 Agent 依赖 ====="

cd "${PROJECT_DIR}/agent"
log "安装 Python 依赖..."
pip3 install -r requirements.txt -q 2>/dev/null || pip3 install -r requirements.txt
log "Agent 依赖安装完成"

# ingestion 依赖
cd "${PROJECT_DIR}"
if [[ -f ingestion/requirements.txt ]]; then
    log "安装 ingestion 依赖..."
    pip3 install -r ingestion/requirements.txt -q 2>/dev/null || true
fi

#==============================================================================
# Step 11: 创建 systemd 服务
#==============================================================================
log "===== Step 11: 创建 systemd 服务 ====="

# Java 后端
cat > /etc/systemd/system/tw-java.service <<EOF
[Unit]
Description=Trading Workstation Java Backend
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}/java
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=/usr/bin/java -Xmx512m -Xms256m -XX:+UseG1GC -jar target/trading-workstation-backend-1.0.0.jar
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/tw-java.log
StandardError=append:/var/log/tw-java.log

[Install]
WantedBy=multi-user.target
EOF

# Next.js 前端
cat > /etc/systemd/system/tw-next.service <<EOF
[Unit]
Description=Trading Workstation Next.js Frontend
After=network.target tw-java.service

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}/next
ExecStart=/usr/bin/npm run start -- -p 3010
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/tw-next.log
StandardError=append:/var/log/tw-next.log

[Install]
WantedBy=multi-user.target
EOF

# Agent 服务
cat > /etc/systemd/system/tw-agent.service <<EOF
[Unit]
Description=Trading Workstation Agent Service
After=network.target tw-java.service

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}/agent
EnvironmentFile=${PROJECT_DIR}/agent/.env
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8100
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/tw-agent.log
StandardError=append:/var/log/tw-agent.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tw-java tw-next tw-agent
log "systemd 服务已创建并设置开机自启"

#==============================================================================
# Step 12: 配置防火墙
#==============================================================================
log "===== Step 12: 配置防火墙 ====="

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22222/tcp  # SSH（改了端口的话）
ufw allow 22/tcp     # SSH（默认端口，保险起见）
ufw allow 80/tcp     # HTTP（Nginx 后续）
ufw allow 443/tcp    # HTTPS（后续）
ufw allow 3010/tcp   # Next.js
ufw allow 8090/tcp   # Java API
ufw --force enable
log "防火墙已配置: $(ufw status | head -1)"

#==============================================================================
# Step 13: 启动服务
#==============================================================================
log "===== Step 13: 启动服务 ====="

log "启动 Java 后端..."
systemctl start tw-java
log "等待 Java 启动（15s）..."
sleep 15

log "启动 Next.js 前端..."
systemctl start tw-next
sleep 5

log "启动 Agent 服务..."
systemctl start tw-agent
sleep 10

#==============================================================================
# Step 14: 健康检查
#==============================================================================
log "===== Step 14: 健康检查 ====="

echo ""
echo "服务状态:"
systemctl status tw-java --no-pager -l | head -5
echo "---"
systemctl status tw-next --no-pager -l | head -5
echo "---"
systemctl status tw-agent --no-pager -l | head -5
echo ""

# API 健康检查
log "API 健康检查..."
JAVA_OK=$(curl -sf http://localhost:8090/TradingWorkstation/actuator/health 2>/dev/null && echo "OK" || echo "FAIL")
NEXT_OK=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:3010/TradingWorkstation 2>/dev/null || echo "FAIL")
AGENT_OK=$(curl -sf http://localhost:8100/api/agent/health 2>/dev/null | grep -o '"status":"ok"' || echo "FAIL")

echo ""
echo "┌──────────────────────────────────────────────────┐"
echo "│              部署结果总览                         │"
echo "├──────────────────────────────────────────────────┤"
printf "│  Java 后端  (8090)  : %-26s │\n" "${JAVA_OK}"
printf "│  Next.js    (3010)  : %-26s │\n" "${NEXT_OK}"
printf "│  Agent      (8100)  : %-26s │\n" "${AGENT_OK}"
echo "├──────────────────────────────────────────────────┤"
printf "│  MySQL 密码  : %-34s │\n" "${DB_PASSWORD:0:16}..."
printf "│  API Key     : %-34s │\n" "${API_KEY:0:16}..."
echo "├──────────────────────────────────────────────────┤"
echo "│  内存使用: $(free -h | awk '/^Mem:/{printf "%s/%s", $3, $2}')              │"
echo "│  Swap 使用: $(free -h | awk '/^Swap:/{printf "%s/%s", $3, $2}')              │"
echo "│  磁盘使用: $(df -h / | awk 'NR==2{printf "%s/%s", $3, $2}')                │"
echo "└──────────────────────────────────────────────────┘"

echo ""
echo -e "${YELLOW}===== 后续步骤 =====${NC}"
echo ""
echo "1. 填入 LLM API Key（Agent AI 功能需要）:"
echo "   cd ${PROJECT_DIR}/agent && nano .env"
echo "   填入: DEVIN_API_KEY / GLM_API_KEY / DEEPSEEK_API_KEY（至少一个）"
echo "   然后重启: systemctl restart tw-agent"
echo ""
echo "2. 导入数据库数据（从本地导出后上传）:"
echo "   本地: mysqldump -u root -proot a_stock_baostock > tw_backup.sql"
echo "   上传: scp -P 22222 tw_backup.sql 服务器IP:/tmp/"
echo "   导入: mysql -u ${DB_USER} -p'${DB_PASSWORD}' ${DB_NAME} < /tmp/tw_backup.sql"
echo ""
echo "3. 查看日志:"
echo "   journalctl -u tw-java -f    # Java 实时日志"
echo "   journalctl -u tw-next -f    # Next.js 实时日志"
echo "   journalctl -u tw-agent -f   # Agent 实时日志"
echo ""
echo "4. 重启服务:"
echo "   systemctl restart tw-java"
echo "   systemctl restart tw-next"
echo "   systemctl restart tw-agent"
echo ""
echo "5. 公网访问:"
echo "   前端: http://服务器公网IP:3010/TradingWorkstation"
echo "   API:  http://服务器公网IP:8090/TradingWorkstation/api/..."
echo ""
echo -e "${GREEN}===== 部署完成！ =====${NC}"
