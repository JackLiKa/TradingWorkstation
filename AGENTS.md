# AGENTS.md — 量化交易工作台

## 项目导航

- `java/` — 后端：Java 21 + Spring Boot 3.3 + Spring Data JPA + Caffeine
  - 入口：`src/main/java/com/quantization/QuantizationApplication.java`
  - 配置：`src/main/resources/application.yml`（从 `.env` 读取）
  - 模块：`com.quantization.module.{stock,indicator,dashboard,screener,backtest,chart,sync,system,preference}`
  - 行業分析：`module.stock` 含行業景氣度、輪動預測、Markov 模型、多模型預測（ARIMA/Holt-Winters/線性回歸）、AutoML 調參、季節性分析、回測驗證
  - 通知服務：`module.system` 含 `NotificationService`（SMTP 郵件 + Webhook，異步推送）
  - 构建：`mvn -DskipTests compile`（需 JDK 21）
  - 运行：`mvn spring-boot:run`，默认 `http://localhost:8090`，Swagger `/swagger-ui.html`
- `next/` — 前端：Next.js 15.1.9 (App Router) + ECharts + shadcn/ui + Tailwind
  - 入口：`src/app/layout.tsx`、`src/app/page.tsx`
  - API 客户端：`src/lib/api/`，类型与后端 DTO 一一对应
  - 构建：`npm run build`（需 `--legacy-peer-deps` 安装，因 SWR peer dep 限制）
  - 运行：`npm run dev`，默认 `http://localhost:3010`
- `agent/` — AI 优化 Agent 服务：FastAPI + LangGraph 风格优化循环 + 多模型 LLM 路由
  - 入口：`agent/app/main.py`
  - 配置：`agent/.env`（从 `agent/.env.example` 复制）
  - LLM 供應商：DeepSeek V4-Pro/Flash、GLM-5.2/4-Flash、Qwen3.6、Qoder、Devin（7 個供應商，按階段性價比路由）
  - 測試：`cd agent && python -m pytest tests/`（173 個測試）
  - 監控：`/api/agent/metrics`（Prometheus 指標端點）
  - 运行：`uvicorn app.main:app`，默认 `http://localhost:8100`，Swagger `/docs`
- `ingestion/` — Python Baostock 数据采集脚本（由后端 sync 模块编排）
- `docs/` — 架构 / API / 数据库文档
- `.env` / `.env.example` — 环境变量（数据库连接、查询默认值、同步配置）

## 服务端口总览

| 服务       | 默认端口 | 配置项              | 说明                     |
|------------|----------|---------------------|--------------------------|
| Java 后端  | 8090     | `SERVER_PORT`       | REST API + Swagger       |
| Next.js 前端 | 3010   | `package.json` 脚本 | App Router SSR/CSR       |
| Agent 服务 | 8100     | `AGENT_PORT`        | AI 优化循环 + LLM 路由   |
| MySQL      | 3306     | `DB_PORT`           | 数据库                   |

## 前置依赖

### 通用依赖

- **JDK 21**（后端必需，推荐 Eclipse Temurin / Microsoft OpenJDK 21）
- **Node.js 18+**（前端必需，推荐 20 LTS）
- **Python 3.10+**（数据同步 + Agent 服务必需）
- **MySQL 8.0+**（数据库，需提前创建库 `a_stock_baostock`）

### 各服务依赖安装

```bash
# 后端 Maven 依赖（首次或 pom.xml 变更后）
cd java && mvn -DskipTests dependency:resolve

# 前端 npm 依赖（首次或 package.json 变更后）
cd next && npm install --legacy-peer-deps

# 数据同步 Python 依赖
pip install -r ingestion/requirements.txt

# Agent 服务 Python 依赖
cd agent && pip install -r requirements.txt
```

### 数据同步配置

- `ingestion/stock_list.json` — 股票清單（3354 隻 A 股，靜態文件）
- `ingestion/index_list.json` — 指數清單（10 大類別 ~80 個指數，含代碼/名稱/分類），不存在時用內置 8 個指數
- `.env` 中 `SYNC_*` 配置項控制後端同步行為

## 完整启动流程

### 启动顺序

**必须按以下顺序启动**，因为存在依赖链：

```
MySQL → Java 后端 (8090) → Next.js 前端 (3010)
                              ↑
Java 后端 (8090) ← Agent 服务 (8100)  ← Agent 依赖后端 REST API
```

1. **MySQL**：确保数据库已启动且 `a_stock_baostock` 库存在。
2. **Java 后端**：前端和 Agent 都依赖后端 API。
3. **Next.js 前端**：用户界面。
4. **Agent 服务**（可选）：AI 策略优化循环，依赖后端回测 API。

### 环境配置（首次启动）

```bash
# 1. 根目录 .env（后端 + 数据同步共用）
cp .env.example .env
# 编辑 .env：填写 DB_PASSWORD、DB_USER 等

# 2. Agent .env（AI 优化服务）
cp agent/.env.example agent/.env
# 编辑 agent/.env：填写 DEVIN_API_KEY 或 QODER_PERSONAL_ACCESS_TOKEN
```

### Windows (PowerShell) 启动方案

#### 方式 A：一键启动脚本（推荐）

每个服务目录下都有 `start.ps1`，自动处理环境变量、依赖检查、端口冲突：

```powershell
# 1. 启动 Java 后端（自动加载 .env + 设置 JDK 21 + 端口冲突检测）
cd "A:\project\Trading Workstation\java"
.\start.ps1

# 2. 启动 Next.js 前端（自动检查 node_modules + 端口冲突检测）
cd "A:\project\Trading Workstation\next"
.\start.ps1

# 3. 启动 Agent 服务（自动选择正确 Python + 加载 agent/.env + 端口冲突检测）
cd "A:\project\Trading Workstation\agent"
.\start.ps1
```

#### 方式 B：手动启动

```powershell
# ===== 0. 设置 JDK 21 路径 =====
# 方式 A：单会话临时设置（每次新终端需重复）
$env:JAVA_HOME = "C:\Users\13026\.jdks\ms-21.0.9"
$env:Path = "$env:JAVA_HOME\bin;$env:Path"

# 方式 B：系统级永久设置（需管理员，只需执行一次）
# Set-ExecutionPolicy Bypass -Scope Process -Force
# cd "A:\project\Trading Workstation"
# .\java\scripts\fix-java21-system.ps1

# 验证 Java 版本（应显示 21.x.x）
java -version

# ===== 1. 启动 Java 后端（端口 8090）=====
# 注意：mvn spring-boot:run 不会自动加载 .env，需先手动加载
Get-Content "A:\project\Trading Workstation\.env" | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.+)$') {
        Set-Item -Path "env:$($matches[1])" -Value $matches[2].Trim('"').Trim("'")
    }
}
cd "A:\project\Trading Workstation\java"
mvn spring-boot:run

# ===== 2. 启动 Next.js 前端（端口 3010，新终端）=====
cd "A:\project\Trading Workstation\next"
npm run dev

# ===== 3. 启动 Agent 服务（端口 8100，新终端，可选）=====
# 注意：用 python 而非 python3（python3 可能指向 Microsoft Store 版本）
cd "A:\project\Trading Workstation\agent"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

### macOS / Linux (Bash) 启动方案

```bash
# ===== 0. 设置 JDK 21 路径（按实际安装路径调整）=====
export JAVA_HOME=$(/usr/libexec/java_home -v 21 2>/dev/null || echo "/usr/lib/jvm/java-21-openjdk")
export PATH="$JAVA_HOME/bin:$PATH"

# ===== 1. 启动 Java 后端（端口 8090）=====
cd "/path/to/Trading Workstation/java"
mvn spring-boot:run
# 或：mvn -DskipTests package && java -Xmx4g -jar target/trading-workstation-backend-1.0.0.jar

# ===== 2. 启动 Next.js 前端（端口 3010，新终端）=====
cd "/path/to/Trading Workstation/next"
npm run dev

# ===== 3. 启动 Agent 服务（端口 8100，新终端，可选）=====
cd "/path/to/Trading Workstation/agent"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

### 验证启动成功

```bash
# 后端健康检查
curl http://localhost:8090/actuator/health
# 期望：{"status":"UP"}

# 前端访问
curl -I http://localhost:3010
# 期望：HTTP/1.1 200

# Agent 健康检查（如已启动）
curl http://localhost:8100/api/agent/health
# 期望：{"provider":"...","available":true,...}

# Swagger 文档
# 后端：http://localhost:8090/swagger-ui.html
# Agent：http://localhost:8100/docs
```

## 数据同步使用说明

### 交互式模式（推荐用户直接使用）

```bash
cd "A:\project\Trading Workstation"
python ingestion/baostock_ingest.py
```

进入交互式菜单，提供 12 个选项：
- 1-4：获取历史数据（2021-01-01 至今），可選單種或全部三種復權
- 5-8：增量更新（只拉缺失數據），可選單種或全部三種復權
- 9-10：指數歷史/增量更新
- 11：增量更新全部（三種復權 + 指數，最常用）
- 12：指定日期範圍 + 全部三種復權 + 指數

### 命令行模式（後端 API 调用）

```bash
# 增量更新全部三種復權 + 指數（最常用，只拉缺失數據）
python ingestion/baostock_ingest.py --mode incremental --adjustflags 1,2,3 --index

# 指定日期範圍全量拉取
python ingestion/baostock_ingest.py --mode range --start 2026-08-17 --end 2026-08-17 --adjustflags 1,2,3 --index

# 只更新特定股票
python ingestion/baostock_ingest.py --mode incremental --codes sh.600000,sz.000001 --adjustflag 3

# 只同步指數
python ingestion/baostock_ingest.py --mode incremental --adjustflags "" --index
```

### 後端 API 同步

```bash
# 啟動同步（增量模式 + 全部三種復權 + 指數）
curl -X POST http://localhost:8090/api/sync/run \
  -H "Content-Type: application/json" \
  -d '{"mode":"incremental","adjustflags":"1,2,3","syncIndex":true}'

# 查詢同步狀態
curl http://localhost:8090/api/sync/status

# 取消同步
curl -X POST http://localhost:8090/api/sync/cancel
```

### 增量更新 vs 日期範圍模式

| 模式 | 參數 | 行為 | 適用場景 |
|------|------|------|----------|
| `incremental` | `--mode incremental` | 每隻股票先查資料庫最新日期，只拉缺失部分 | 日常更新（速度快） |
| `range` | `--mode range --start YYYY-MM-DD --end YYYY-MM-DD` | 拉取指定日期範圍的全部數據 | 補數據、首次導入 |

### 復權類型

| adjustflag | 含義 | 說明 |
|------------|------|------|
| 1 | 後復權 | 以最早數據為基準，向前調整 |
| 2 | 前復權 | 以最新數據為基準，向後調整 |
| 3 | 不復權 | 原始價格 |

### 寫入策略

- `stock_daily` 表：`ON DUPLICATE KEY UPDATE`，唯一鍵 `(code, date, adjustflag)`
- `index_daily` 表：`ON DUPLICATE KEY UPDATE`，唯一鍵 `(code, date, frequency)`
- 重複運行安全，不會產生重複數據

### Baostock 會話超時處理

Baostock 長時間查詢會出現「用戶未登錄」錯誤。腳本已實現自動重新登錄機制（`_ensure_login()`），無需人工干預。

## 进程冲突与端口占用解决方案

### 检查端口占用

```powershell
# Windows (PowerShell)
netstat -ano | findstr ":8090"
netstat -ano | findstr ":3010"
netstat -ano | findstr ":8100"
# 最后一列是 PID，用以下命令查看进程名：
Get-Process -Id <PID>
```

```bash
# macOS / Linux
lsof -i :8090
lsof -i :3010
lsof -i :8100
# 或：ss -tlnp | grep 8090
```

### 终止占用进程

```powershell
# Windows (PowerShell) — 按端口找 PID 再终止
$pid_8090 = (Get-NetTCPConnection -LocalPort 8090 -ErrorAction SilentlyContinue).OwningProcess
if ($pid_8090) { Stop-Process -Id $pid_8090 -Force }

# 或按进程名终止所有 Java 进程（谨慎：会杀掉所有 Java 应用）
Get-Process -Name java -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force
```

```bash
# macOS / Linux
kill $(lsof -t -i:8090)
# 或强制：
kill -9 $(lsof -t -i:8090)
pkill -f "trading-workstation-backend"
pkill -f "next dev"
pkill -f "uvicorn app.main:app"
```

### 常见进程冲突报错

| 报错信息 | 原因 | 解决方案 |
|----------|------|----------|
| `Port 8090 was already in use` | 后端端口被占用 | 终止占用进程或修改 `SERVER_PORT` |
| `EADDRINUSE: address already in use 0.0.0.0:3010` | 前端端口被占用 | 终止占用进程或改 `next dev -p <其他端口>` |
| `Address already in use: 8100` | Agent 端口被占用 | 终止占用进程或修改 `AGENT_PORT` |
| `Unable to rename '...jar' to '...jar.original'` | Maven 重新打包时旧 jar 被锁 | 先终止运行中的 Java 进程再 `mvn package` |
| `Communications link failure` | MySQL 未启动或连接信息错误 | 检查 MySQL 服务 + `.env` 中 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD` |
| `Access denied for user 'root'` | 数据库密码错误 | 修正 `.env` 中 `DB_PASSWORD` |
| `No Java runtime found` | `JAVA_HOME` 未设置或路径错误 | 设置 `JAVA_HOME` 指向 JDK 21 安装目录 |
| `NoClassDefFoundError: SpringApplication` | Maven `settings.xml` 本地仓库路径含非 ASCII 字符（如中文），`spring-boot:run` fork JVM 时 classpath 编码损坏 | 将本地仓库路径改为纯 ASCII（见下方「Maven settings.xml 常见问题」） |
| `NullPointerException: adjustflag() is null` | 回测请求未传 `adjustflag`，DTO 字段为 `Integer`（可为 null） | 已修复：`BacktestService` 对 null 提供默认值 3 |
| `TypeError: ResultData.get_row_data() takes 1 positional argument but 2 were given` | `baostock_ingest.py` 的 `_all_codes()` 用了错误的 API 调用方式 | 已修复：改用 `rs.next()` 迭代 + `rs.get_row_data()` 无参调用 |
| `settings.xml: Unrecognised tag: 'profile'` | `<profile>` 写在 `<profiles>` 标签外面，非法 XML 结构 | 将 `<profile>` 移入 `<profiles>` 内或删除非法 profile |

## Java 21 环境配置

### 当前项目要求

- **JDK 21**（后端必需，推荐 Microsoft OpenJDK 21 / Eclipse Temurin 21）
- 项目 `pom.xml` 中 `<java.version>21</java.version>` + `<maven.compiler.release>21</maven.compiler.release>`

### Windows 系统级配置（需管理员权限）

项目根目录提供了 `fix-java21-system.ps1` 脚本，以管理员身份运行：

```powershell
# 右键 PowerShell → 以管理员身份运行
Set-ExecutionPolicy Bypass -Scope Process -Force
cd "A:\project\Trading Workstation"
.\fix-java21-system.ps1
```

脚本会：
1. 设置 System 级 `JAVA_HOME` → JDK 21 路径
2. 清理 System PATH 中的旧 Java 路径（Oracle javapath、Java 8、Java 17 等）
3. 将 `%JAVA_HOME%\bin` 置于 System PATH 最前面

### 手动配置（单会话临时生效）

```powershell
$env:JAVA_HOME = "C:\Users\13026\.jdks\ms-21.0.9"
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
java -version  # 确认显示 21.x.x
```

### 多版本 JDK 共存

系统可能安装了多个 JDK（8/11/17/21/23），通过 PATH 顺序决定默认版本。常见冲突：

| 冲突来源 | 影响 | 解决方案 |
|----------|------|----------|
| `C:\Program Files\Common Files\Oracle\Java\javapath` | System PATH 优先级高，指向 Oracle JRE | 从 System PATH 移除，改用 `%JAVA_HOME%\bin` |
| `C:\jdk-17.0.13...\bin` | Java 17 排在 Java 21 前面 | 从 PATH 移除或调整顺序 |
| User PATH 中的旧 JDK 路径 | 覆盖 System PATH | 清理 User PATH 中的旧 Java 路径 |

## Maven settings.xml 常见问题

### 本地仓库路径含非 ASCII 字符

**问题**：`settings.xml` 中 `<localRepository>` 路径含中文（如 `MAVEN的local repository`），Maven 内部解析依赖时编码正确，但 `spring-boot:run` fork JVM 传 classpath 时编码损坏，导致 `NoClassDefFoundError`。

**症状**：
- `mvn clean install` / `mvn package` 成功
- `mvn spring-boot:run` 失败：`NoClassDefFoundError: org/springframework/boot/SpringApplication`
- debug 日志中 classpath 路径中文变成乱码（如 `的` → `—`）

**解决**：
1. 重命名本地仓库目录为纯 ASCII（如 `maven-repo`）
2. 修改 `settings.xml` 中 `<localRepository>` 为纯 ASCII 路径
3. 将 `settings.xml` 保存为 UTF-8 编码

### 非法 `<profile>` 结构

**问题**：`<profile>` 标签写在 `<profiles>` 标签外面，违反 XML 结构。

**症状**：Maven 启动时 WARNING：`Unrecognised tag: 'profile'`

**解决**：将 `<profile>` 移入 `<profiles>` 内，或直接删除非法 profile 块。

### settings.xml 编码

`settings.xml` 应保存为 **UTF-8 无 BOM**。GBK 编码的中文注释在 Maven 某些场景下会导致解析异常。

## 缓存带来的错误影响与处理

### 后端 Caffeine 缓存

后端使用 Caffeine 内存缓存（`CacheConfig.java`），涉及以下缓存：

| 缓存名              | TTL（秒）           | 缓存内容          | 清除触发条件         |
|---------------------|---------------------|-------------------|----------------------|
| `dashboardSummary`    | `CACHE_SUMMARY_TTL_SECONDS`（默认 60）   | 仪表盘汇总数据       | TTL 过期自动清除     |
| `dashboardMetrics`    | `CACHE_METRICS_TTL_SECONDS`（默认 30）   | 仪表盘指标           | TTL 过期自动清除     |
| `indexMetadata`       | `CACHE_METRICS_TTL_SECONDS`（默认 30）   | 指數元數據           | TTL 过期自动清除     |
| `marketBreadth`       | `CACHE_METRICS_TTL_SECONDS`（默认 30）   | 市場廣度分析         | TTL 过期自动清除     |
| `rotationSignal`      | `CACHE_METRICS_TTL_SECONDS`（默认 30）   | 輪動信號分析         | TTL 过期自动清除     |
| `sectorPerformance`   | `CACHE_METRICS_TTL_SECONDS`（默认 30）   | 多日板塊表現         | TTL 过期自动清除     |
| `industryDailyCache`  | 300（5 分鐘）        | 行業景氣度/輪動預測/Markov/多模型預測/回測/AutoML/季節性等分析結果 | TTL 过期自动清除 |

**缓存可能导致的错误现象：**

1. **数据同步后仪表盘数据不更新**：同步写入新数据后，仪表盘仍显示旧数据，因为缓存未过期。
   - **解决**：等待 TTL 过期（默认 30~60 秒），或重启后端，或临时调小 `CACHE_*_TTL_SECONDS`。
2. **修改数据库后查询结果不变**：直接在 MySQL 中改数据不会清缓存。
   - **解决**：通过 API 操作（走 Service 层）或重启后端。
3. **不同用户看到不同数据**：Caffeine 是本地缓存，多实例部署时会不一致。
   - **解决**：单实例部署无此问题；多实例需改用 Redis 等分布式缓存。

**开发调试时临时禁用缓存：**

在 `.env` 中设置：
```dotenv
CACHE_SUMMARY_TTL_SECONDS=0
CACHE_METRICS_TTL_SECONDS=0
```
> 注意：TTL=0 时 Caffeine 行为是「立即过期」，相当于禁用，但仍有少量开销。

### 前端 SWR 缓存

前端使用 SWR 做数据请求缓存，默认会缓存请求结果。

**可能导致的错误现象：**

1. **切换页面后显示旧数据**：SWR 默认 `revalidateOnFocus=true`，但短时间内可能命中缓存。
   - **解决**：刷新页面，或在 SWR 配置中调整 `dedupingInterval` / `refreshInterval`。
2. **数据同步后前端不刷新**：同步状态通过轮询 `/api/sync/status`，同步完成后需手动刷新仪表盘。
   - **解决**：在同步完成回调中调用 `mutate()` 触发 SWR 重新请求。

### Maven / npm 缓存

**Maven 依赖缓存问题**：修改 `pom.xml` 后编译报错找不到新依赖。
```powershell
# 清理 Maven 本地仓库缓存（谨慎：会重新下载所有依赖）
mvn dependency:purge-local-repository -DreResolve=true
# 或只清理本项目
cd java && mvn clean
```

**npm 缓存问题**：`npm install` 后 `npm run dev` 报模块找不到。
```bash
cd next
rm -rf node_modules .next package-lock.json  # Windows: rmdir /s /q node_modules .next
npm cache clean --force
npm install --legacy-peer-deps
```

**Python pip 缓存问题**：安装旧版本依赖。
```bash
pip install --no-cache-dir -r requirements.txt
```

### Next.js 构建缓存

**`.next` 缓存导致类型错误或页面异常**：
```bash
cd next
rm -rf .next    # Windows: rmdir /s /q .next
npm run dev     # 重新构建
```

## 构建与验证命令

```bash
# 后端（需 JDK 21）
cd java
mvn -DskipTests compile          # 编译
mvn -DskipTests package          # 打包 jar
mvn spring-boot:run              # 运行（开发）
mvn test                         # 运行测试

# 前端
cd next
npm install --legacy-peer-deps   # 安装
npx tsc --noEmit                 # 类型检查
npm run lint                     # ESLint
npm run build                    # 生产构建
npm run dev                      # 开发运行

# Agent 服务
cd agent
pip install -r requirements.txt  # 安装依赖
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100  # 运行

# 数据同步脚本（独立测试）
python ingestion/baostock_ingest.py --codes sh.600000 --start 2026-08-01 --end 2026-08-14
```

## 关键约定

- **统一响应**：所有 API 返回 `ApiResponse<T>` = `{success, code, message, data}`
- **DTO 对齐**：`next/src/lib/api/types.ts` 与 `java/.../module/*/dto` 字段一一对应，camelCase
- **指标计算**：在 Java `IndicatorEngine` 忠实移植原 Python 公式，前端不重复计算（图表叠加用后端返回的序列）
- **配置**：`.env` → `application.yml` 占位符 → `@ConfigurationProperties`；密钥不入库
- **数据同步**：Java `SyncService` 通过 `ProcessBuilder` 编排 `ingestion/baostock_ingest.py`，已强制 `PYTHONIOENCODING=utf-8` 以确保 Windows 下中文进度行正确解析
- **Agent 优化链路**：Agent 调用后端 `/api/backtest/run`（内部已含 `ScreenerCore.screenAt`），不单独调用选股接口，避免重复筛选
- **原项目**：`Quantization/` 为原 PySide6 桌面端，保留作为参考

## 安全注意

- `.env` 已加入 `.gitignore`，不入库
- `agent/.env` 已加入 `.gitignore`，不入库
- 原 `Quantization/database.md` 与 `.env.example` 中的明文密码不应复制到新实现
- 建议轮换已暴露的数据库密码
- `DEVIN_API_KEY` 与 `QODER_PERSONAL_ACCESS_TOKEN` 为敏感凭证，禁止写入代码、日志、提交信息

---

## 工程標準（Engineering Standards）

> 以下章節參考 ECC（Everything Claude Code）項目的工程規範，結合本項目技術棧落地。

### 核心原則

1. **計劃先行** — 複雜功能先規劃再實作，識別依賴和風險，拆分為可驗證的階段
2. **測試驅動** — 新功能先寫測試（RED），再寫最小實現（GREEN），最後重構（IMPROVE）
3. **安全至上** — 永不硬編碼密鑰；所有外部輸入必須校驗；提交前執行安全 checklist
4. **不可變優先** — 優先創建新對象而非修改共享狀態，減少副作用
5. **高內聚低耦合** — 按功能/領域組織文件，而非按類型；模組邊界清晰

### 編碼風格

**文件組織**：多個小文件優於少數大文件。單文件 200-400 行為宜，不超過 800 行。按功能/領域組織，高內聚低耦合。

**函數規範**：
- 函數體 < 50 行
- 嵌套不超過 4 層
- 命名清晰可讀，避免縮寫
- 無硬編碼值（用配置或常量）

**錯誤處理**：
- 每一層都要處理錯誤，不可靜默吞掉
- UI 層提供用戶友好消息
- 服務端記錄詳細上下文日誌
- 系統邊界（API 入口）必須校驗輸入，fail fast

**語言特定規範**：

| 語言 | 規範 | Lint 工具 |
|------|------|-----------|
| Java | Google Java Style Guide + Lombok | Maven compiler warnings |
| TypeScript | ESLint + 函數式組件 + Hooks | `npx eslint src/` |
| Python | PEP 8 + 類型注解 | `ruff check` |

### 測試要求

**最低覆蓋率目標：80%**（逐步達成，新代碼必須有測試）

測試類型（全部需要）：

| 類型 | 範圍 | 工具 | 運行命令 |
|------|------|------|----------|
| 單元測試 | 函數、工具類、組件 | pytest / JUnit / Jest | 見下方 |
| 整合測試 | API 端點、數據庫操作 | pytest / Testcontainers | 見下方 |
| E2E 測試 | 關鍵用戶流程 | 手動 / Playwright（未來） | — |

```bash
# Agent 單元 + 整合測試
cd agent && python -m pytest tests/ -v --tb=short

# Java 編譯驗證（測試待補）
cd java && mvn -B -DskipTests compile

# 前端類型檢查 + lint + 構建
cd next && npx tsc --noEmit && npx eslint src/ && npm run build
```

**TDD 工作流（新功能必須遵循）**：
1. **RED** — 先寫測試，測試應該失敗
2. **GREEN** — 寫最小實現讓測試通過
3. **IMPROVE** — 重構，確認覆蓋率 ≥ 80%

測試失敗排查順序：檢查測試隔離 → 驗證 mock → 修復實現（除非測試本身有誤）。

### 開發工作流

```
1. 計劃  → 識別依賴和風險，拆分為階段
2. TDD   → 先寫測試，再實作，最後重構
3. 審查  → 自審 CRITICAL/HIGH 問題，參考 RULES.md checklist
4. 文檔  → 更新相關文檔（API/架構/數據庫），不重複已有信息
5. 提交  → Conventional Commits 格式，PR 附測試計劃
```

### Git 工作流

**提交格式**：`<type>(<scope>): <description>`

類型：`feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

**PR 流程**：
1. 分析完整 commit 歷史
2. 撰寫全面摘要（Summary + Test plan）
3. 使用 `git push -u origin <branch>` 推送

**分支策略**：
- `main` — 主分支，保持可運行狀態
- `feat/<name>` — 新功能分支
- `fix/<name>` — Bug 修復分支
- `docs/<name>` — 文檔分支

### 架構模式

**API 響應格式**：統一信封 `ApiResponse<T>` = `{success, code, message, data}`

**Repository 模式**：數據訪問封裝在 Repository 層（`findAll`, `findById`, `create`, `update`, `delete`），業務邏輯依賴抽象接口而非存儲機制。

**服務分層**：
```
Controller（API 邊界，輸入校驗）
    ↓
Service（業務邏輯，事務管理）
    ↓
Repository（數據訪問，持久化）
    ↓
Entity / DTO（數據模型）
```

**Agent 編排模式**：
```
Optimizer（循環編排）
    ↓
Stage Base（階段基類，供應商路由 + JSON mode）
    ↓
LLM Client（多模型路由 + 自動降級）
    ↓
Backend Client（REST API 調用 + 重試 + 速率限制）
```

### 安全規範

**提交前必須檢查**（完整 checklist 見 `RULES.md`）：
- 無硬編碼密鑰（API Key、密碼、Token）
- 所有用戶輸入已校驗
- SQL 使用參數化查詢（JPA 已內建）
- 錯誤消息不洩露敏感信息
- `.env` / `agent/.env` 不在暫存區

**密鑰管理**：
- 永不硬編碼密鑰，使用環境變量
- 啟動時校驗必需密鑰是否存在
- 已暴露的密鑰必須立即輪換

**發現安全問題時**：
```
停止 → 評估影響 → 修復 CRITICAL 問題 → 輪換已暴露密鑰 → 排查類似問題
```

### 性能與上下文管理

- 數據庫查詢避免 N+1，用 `@EntityGraph` 或 JOIN FETCH
- Caffeine 緩存 TTL 根據數據更新頻率配置
- Agent LLM 調用使用速率限制器（令牌桶）防止壓垮後端
- 前端 SWR 輪詢間隔根據頁面活躍度調整（運行時 2s，空閒 10s）

### 項目結構

```
java/           — Java 21 + Spring Boot 後端
next/           — Next.js 15 前端
agent/          — FastAPI AI 優化服務
ingestion/      — Baostock 數據採集
docs/           — 架構 / API / 數據庫文檔
.github/        — CI/CD + Issue/PR 模板
```

### 成功指標

- 所有測試通過，覆蓋率 ≥ 80%
- 無安全漏洞（gitleaks 掃描通過）
- 代碼可讀、可維護
- 性能可接受（API 響應 < 500ms，回測 < 30s）
- 用戶需求已滿足
