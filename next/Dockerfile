# Next.js 前端 Dockerfile — 多階段構建
# 構建: docker build -t tw-next ./next
# 運行: 由 docker-compose 編排

# ===== Stage 1: Dependencies =====
FROM node:20-alpine AS deps

WORKDIR /app

# 複製 package 文件利用 Docker 緩存層
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps

# ===== Stage 2: Build =====
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# 構建時需要後端地址（用於 API 代理配置）
ARG BACKEND_HOST=http://localhost:8090
ENV BACKEND_HOST=$BACKEND_HOST

RUN npm run build

# ===== Stage 3: Runtime =====
FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3010

# 只複製生產所需文件
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3010

# Next.js standalone 模式啟動
CMD ["node", "server.js"]
