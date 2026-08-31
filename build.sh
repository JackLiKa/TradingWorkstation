#!/bin/bash
#==============================================================================
# Trading Workstation — Docker 镜像一键构建脚本
#
# 在本地（Windows/Mac/Linux）运行，构建所有服务镜像并导出为 tar 包，
# 传输到云服务器后用 deploy-docker.sh 部署。
#
# 用法:
#   ./build.sh              # 构建全部 + 导出 tar
#   ./build.sh --no-export  # 只构建，不导出 tar
#   ./build.sh --load       # 构建后直接 docker load 到本地（用于本地测试）
#
# 前置条件:
#   - Docker 已安装并运行
#   - 项目根目录有 .env 文件（或至少 DB_PASSWORD 已设置）
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

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 参数解析
EXPORT_TAR=true
LOAD_LOCAL=false
for arg in "$@"; do
    case $arg in
        --no-export) EXPORT_TAR=false ;;
        --load)      LOAD_LOCAL=true; EXPORT_TAR=false ;;
        --help|-h)
            echo "用法: ./build.sh [--no-export|--load]"
            echo "  默认: 构建全部镜像 + 导出 tar 到 dist/"
            echo "  --no-export: 只构建，不导出"
            echo "  --load: 构建后直接加载到本地 Docker（用于本地测试）"
            exit 0 ;;
    esac
done

# 版本号：使用 git short hash，无 git 则用时间戳
VERSION=$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)
REGISTRY="${REGISTRY:-}"  # 可选：设置 REGISTRY 推送到远程仓库

log "===== Trading Workstation Docker 镜像构建 ====="
log "版本: ${VERSION}"
log "导出 tar: ${EXPORT_TAR}"
log ""

# 检查 Docker
if ! docker info >/dev/null 2>&1; then
    err "Docker 未运行，请先启动 Docker"
    exit 1
fi

# 镜像列表
IMAGES=(
    "tw-java:${VERSION}"
    "tw-next:${VERSION}"
    "tw-agent:${VERSION}"
)

#==============================================================================
# Step 1: 构建 Java 后端镜像
#==============================================================================
log "===== [1/3] 构建 Java 后端镜像 ====="
docker build \
    --platform linux/amd64 \
    -t "tw-java:${VERSION}" \
    -t "tw-java:latest" \
    -f java/Dockerfile \
    java/
log "Java 镜像构建完成: tw-java:${VERSION}"

#==============================================================================
# Step 2: 构建 Next.js 前端镜像
#==============================================================================
log "===== [2/3] 构建 Next.js 前端镜像 ====="
docker build \
    --platform linux/amd64 \
    -t "tw-next:${VERSION}" \
    -t "tw-next:latest" \
    -f next/Dockerfile \
    next/
log "Next.js 镜像构建完成: tw-next:${VERSION}"

#==============================================================================
# Step 3: 构建 Agent 镜像（含 a-share-mcp）
#==============================================================================
# Agent Dockerfile 需要 a-share-mcp 源码，build context 设为项目根目录
log "===== [3/3] 构建 Agent 镜像（含 a-share-mcp 子服务）====="
docker build \
    --platform linux/amd64 \
    -t "tw-agent:${VERSION}" \
    -t "tw-agent:latest" \
    -f agent/Dockerfile \
    .
log "Agent 镜像构建完成: tw-agent:${VERSION}"

#==============================================================================
# Step 4: 导出 tar 包（用于传输到无 Docker registry 的服务器）
#==============================================================================
if [ "$EXPORT_TAR" = true ]; then
    log "===== 导出镜像 tar 包 ====="
    mkdir -p dist

    for img in "${IMAGES[@]}"; do
        filename="dist/$(echo "$img" | tr '/:' '__').tar"
        log "导出 $img → $filename"
        docker save "$img" -o "$filename"
    done

    # 打包为单个 tar.gz
    ARCHIVE="dist/tw-images-${VERSION}.tar.gz"
    log "压缩为 $ARCHIVE"
    tar -czf "$ARCHIVE" \
        -C dist \
        tw-java_${VERSION}.tar \
        tw-next_${VERSION}.tar \
        tw-agent_${VERSION}.tar

    # 清理中间 tar 文件
    rm -f dist/tw-java_${VERSION}.tar dist/tw-next_${VERSION}.tar dist/tw-agent_${VERSION}.tar

    log ""
    log "导出完成！文件位于 dist/ 目录："
    ls -lh dist/
    log ""
    log "传输到服务器："
    log "  scp dist/tw-images-${VERSION}.tar.gz ubuntu@<server-ip>:/tmp/"
    log "  然后在服务器上运行："
    log "  sudo bash deploy-docker.sh /tmp/tw-images-${VERSION}.tar.gz ${VERSION}"
fi

if [ "$LOAD_LOCAL" = true ]; then
    log "镜像已加载到本地 Docker，可用 docker-compose up -d 启动"
fi

log ""
log "===== 全部构建完成 ====="
log "镜像列表："
docker images | grep "tw-" | head -10
