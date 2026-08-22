# Trading Workstation — A 股量化交易工作台

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Java](https://img.shields.io/badge/Java-21-orange.svg)](https://openjdk.org/projects/jdk/21/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.3.4-green.svg)](https://spring.io/projects/spring-boot)
[![Next.js](https://img.shields.io/badge/Next.js-15.1.9-black.svg)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1.svg)](https://www.mysql.com/)

> **A 股量化交易工作台** — 含行情採集、技術指標、條件選股、策略回測、AI 優化。
> 由原 PySide6 桌面端項目 ([Quantization](https://github.com/JackLiKa/Quantization.git)) 重構而來，保持全部功能並做性能優化與 AI 策略優化集成。

**[快速開始](#快速開始)** • **[架構概覽](#架構概覽)** • **[文檔導航](#文檔導航)** • **[開發](#開發)** • **[部署](#部署)** • **[License](#license)**

---

## 項目簡介

Trading Workstation 是一個**單機/小團隊自用**的 A 股量化研究工作台，覆蓋從數據採集到 AI 策略優化的完整閉環：

- **行情採集** — Baostock 日線（3 種復權）+ 540 個指數 + 行業分類，冪等寫入 MySQL
- **技術指標** — MA/EMA/BOLL/MACD/KDJ/RSI 等，註冊表模式可擴展
- **條件選股** — 49 字段條件組合篩選，全市場 parallelStream 過濾
- **策略回測** — 等權調倉 + 滑點 + 漲跌停約束 + 夏普減無風險利率 + 結果自動落庫
- **行業分析** — 景氣度/輪動/Markov/多模型預測（ARIMA/Holt-Winters/線性回歸）/AutoML/季節性
- **AI 優化** — 6 階段 AI 循環（分析→生成→驗證→回測→評分→反思），7 個 LLM 供應商按階段性價比路由

## 快速開始

### 前置依賴

| 依賴 | 版本 | 用途 |
|------|------|------|
| JDK | 21+（推薦 Eclipse Temurin / Microsoft OpenJDK 21） | 後端 |
| Node.js | 18+（推薦 20 LTS） | 前端 |
| Python | 3.10+ | 數據採集 + Agent 服務 |
| MySQL | 8.0+ | 數據庫（需提前建庫 `a_stock_baostock`） |
| Maven | 3.9+ | 後端構建 |

### 3 步驟啟動

```bash
# 1. 克隆倉庫
git clone https://github.com/JackLiKa/TradingWorkstation.git
cd TradingWorkstation

# 2. 配置環境變量
cp .env.example .env                    # 後端 + 數據採集共用
#   編輯 .env，填寫 DB_PASSWORD 等
cp agent/.env.example agent/.env        # Agent 服務（可選）
#   編輯 agent/.env，填寫至少一個 LLM API key

# 3. 按順序啟動服務（存在依賴鏈：MySQL → Java → Next → Agent）
```

**啟動順序**（必須遵守，存在依賴鏈）：

```
MySQL → Java 後端 (8090) → Next.js 前端 (3010)
                ↑
         Agent 服務 (8100)  ← Agent 依賴後端 REST API
```

```powershell
# Windows (PowerShell) — 每個服務目錄下有一鍵腳本 start.ps1
cd java;  .\start.ps1     # 1. Java 後端（自動加載 .env + JDK21 + 端口檢測）
cd next;  .\start.ps1     # 2. Next.js 前端（新終端）
cd agent; .\start.ps1     # 3. Agent 服務（新終端，可選）
```

```bash
# macOS / Linux (Bash)
export JAVA_HOME=$(/usr/libexec/java_home -v 21 2>/dev/null || echo "/usr/lib/jvm/java-21-openjdk")
export PATH="$JAVA_HOME/bin:$PATH"
cd java  && mvn spring-boot:run                          # 1. Java 後端
cd next  && npm install --legacy-peer-deps && npm run dev # 2. Next.js 前端
cd agent && python3 -m uvicorn app.main:app --port 8100   # 3. Agent 服務（可選）
```

### 驗證啟動

```bash
curl http://localhost:8090/TradingWorkstation/actuator/health   # → {"status":"UP"}
curl -I http://localhost:3010/TradingWorkstation                # → HTTP/1.1 200
curl http://localhost:8100/api/agent/health                     # → {"available":true,...}
```

> **首次使用需導入數據**：`pip install -r ingestion/requirements.txt` → `python ingestion/baostock_ingest.py`（選菜單 11 增量更新全部）。詳見 [`ingestion/README.md`](./ingestion/README.md)。

## 架構概覽

4 個自研服務 + 1 個數據庫 + 可選監控棧，後端按業務域拆分為 **12 個模塊**：

```
瀏覽器 → Next.js 前端 (:3010)  ──rewrites──→  Java 後端 (:8090)  ──JPA──→  MySQL (:3306)
                    │                              ↑
                    └──rewrites──→  Agent 服務 (:8100)  ──REST──┘
                                         │
                                         └──→  LLM 供應商 ×7
```

**後端 12 模塊**（`com.quantization.module.*`）：

| 模塊 | 職責 |
|------|------|
| `stock` | 行情查詢（26 端點）、指數行情、行業日聚合 |
| `industry` | 行業景氣度、輪動信號、異常預警 |
| `forecast` | 預測（ARIMA/Holt-Winters/線性回歸）、Markov、AutoML、季節性 |
| `indicator` | 指標引擎（註冊表模式，MA/BOLL/MACD/KDJ/RSI…），純計算無持久化 |
| `dashboard` | 儀表盤聚合（複用 stock/chart） |
| `chart` | K 線分批加載（120 條/批 + 內嵌指標） |
| `screener` | 選股器（49 字段條件、parallelStream 過濾） |
| `backtest` | 回測引擎 + 策略庫（滑點+漲跌停+落庫） |
| `sync` | ProcessBuilder 編排 ingestion Python 腳本 |
| `system` | 健康檢查、DB 配置、通知（SMTP+Webhook） |
| `preference` | 用戶偏好（DB 主存 + 文件降級） |
| `aicalllog` | AI 調用日誌（agent 回寫，供可視化） |

> 完整架構設計、C4 圖、數據流詳見 [`docs/architecture.md`](./docs/architecture.md)。

## 服務端口表

| 服務 | 默認端口 | 前綴 | 配置項 | 說明 |
|------|----------|------|--------|------|
| Java 後端 | 8090 | `/TradingWorkstation` | `SERVER_PORT` | REST API + Swagger `/swagger-ui.html` |
| Next.js 前端 | 3010 | `basePath: /TradingWorkstation` | `package.json` | App Router SSR/CSR |
| Agent 服務 | 8100 | `/api/agent` | `AGENT_PORT` | AI 優化循環 + LLM 路由，Swagger `/docs` |
| MySQL | 3306 | — | `DB_PORT` | 庫名 `a_stock_baostock` |
| Prometheus | 9090 | — | docker-compose | 可選監控（scrape agent /metrics） |
| Grafana | 3000 | — | docker-compose | 可選儀表盤 |

> **⚠️ context-path 契約鏈**：`/TradingWorkstation` 前綴必須在三處同步——後端 `application.yml`、前端 `next.config.js` basePath+rewrites、agent `BACKEND_API_URL`。詳見 [`docs/architecture.md`](./docs/architecture.md)。

## 技術棧一覽

| 層 | 選型 |
|----|------|
| 後端 | Java 21、Spring Boot 3.3.4、Spring Data JPA (Hibernate 6.5)、HikariCP、Caffeine、springdoc-openapi、Lombok、Spring Mail |
| 前端 | Next.js 15.1.9 (App Router)、React 19、TypeScript 5.6、Tailwind CSS、shadcn/ui、ECharts 5.5、SWR、Zustand |
| AI Agent | Python 3.10+、FastAPI、Uvicorn、LangGraph 風格優化循環、多模型 LLM 路由（7 供應商）、Milvus Lite (RAG)、Prometheus |
| 數據庫 | MySQL 8.0+（8 張表：stock_daily / index_daily / index_metadata / stock_industry / industry_daily / backtest_strategy / user_preference / ai_call_log） |
| 數據採集 | Python Baostock 腳本（三模塊拆分：fetch + write + ingest），Java SyncService 通過 ProcessBuilder 編排 |
| 通知 | Spring Mail (SMTP) + Webhook（景氣度預警，異步推送） |

## 文檔導航

### 架構與設計

- [`docs/architecture.md`](./docs/architecture.md) — 系統架構與模塊設計（C4 圖、服務拓撲、context-path 契約鏈）
- [`docs/MODULE_GUIDE.md`](./docs/MODULE_GUIDE.md) — 12 模塊逐一說明（端點、分層、緩存、依賴）
- [`docs/database.md`](./docs/database.md) — 數據庫 Schema（8 張表、索引、ER 圖）

### API 與引擎

- [`docs/api.md`](./docs/api.md) — REST API 參考（後端 51 端點 + Agent 22 端點）
- [`docs/BACKTEST_ENGINE.md`](./docs/BACKTEST_ENGINE.md) — 回測引擎原理與使用指南
- [`docs/AGENT_SERVICE.md`](./docs/AGENT_SERVICE.md) — Agent 服務詳解（LLM 路由、優化循環、RAG）

### 數據與運維

- [`docs/DATA_INGESTION.md`](./docs/DATA_INGESTION.md) — 數據採集完整指南（含前復權陳舊化對策）
- [`docs/DEVELOPMENT.md`](./docs/DEVELOPMENT.md) — 開發指南（規範、構建命令、變更清單）
- [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) — 部署指南（環境變量、Docker Compose、故障排查）

### 子模塊 README

- [`java/README.md`](./java/README.md) — 後端模塊說明（12 模塊、構建、關鍵設計）
- [`next/README.md`](./next/README.md) — 前端模塊說明（路由、API 客戶端、ECharts 封裝）
- [`agent/README.md`](./agent/README.md) — Agent 服務說明（6 階段、7 供應商、多窗口評分）
- [`ingestion/README.md`](./ingestion/README.md) — 數據採集說明（三模塊、CLI、進度協議）

### 其他

- [`AGENTS.md`](./AGENTS.md) — 項目導航與開發規範（AI 協作指南）
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — 貢獻指南
- [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) — 行為準則
- [`SECURITY.md`](./SECURITY.md) — 安全政策

## 開發

構建命令、代碼規範、變更清單（改一處要同步哪些地方）詳見 [`docs/DEVELOPMENT.md`](./docs/DEVELOPMENT.md)。

快速驗證：

```bash
cd java  && mvn -DskipTests compile          # 後端編譯（需 JDK 21）
cd next  && npm run build && npm run lint     # 前端構建 + lint
cd agent && python -m pytest tests/           # Agent 測試（197 個）
cd java  && mvn test                          # 後端測試（80 個）
cd next  && npm run test                      # 前端測試（24 個 vitest）
```

## 部署

環境變量、Docker Compose 全棧部署、故障排查詳見 [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md)。

Docker 一鍵啟動：

```bash
docker-compose up -d    # mysql + java + next + agent + prometheus + grafana
```

## License

本项目基於 [MIT License](LICENSE) 開源，僅供學習和個人使用。
