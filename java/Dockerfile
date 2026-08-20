# Java 後端 Dockerfile — 多階段構建
# 構建: docker build -t tw-java ./java
# 運行: 由 docker-compose 編排

# ===== Stage 1: Build =====
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /build

# 先複製 pom.xml 利用 Docker 緩存層
COPY pom.xml .
RUN mvn -B -DskipTests dependency:resolve

# 複製源碼並構建
COPY src ./src
RUN mvn -B -DskipTests package

# ===== Stage 2: Runtime =====
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# 從 builder 階段複製 jar
COPY --from=builder /build/target/trading-workstation-backend-1.0.0.jar app.jar

# 安裝 curl 用於健康檢查
RUN apk add --no-cache curl

# 環境變量默認值（由 docker-compose 覆蓋）
ENV SERVER_PORT=8090 \
    SERVER_CONTEXT_PATH=/TradingWorkstation \
    JAVA_OPTS="-Xmx4g -Xms512m"

EXPOSE 8090

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=60s \
  CMD curl -f http://localhost:8090/TradingWorkstation/actuator/health || exit 1

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
