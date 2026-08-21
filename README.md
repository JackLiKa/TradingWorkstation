# 量化交易工作台 (Trading Workstation)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Java](https://img.shields.io/badge/Java-21-orange.svg)](https://openjdk.org/projects/jdk/21/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.3.4-green.svg)](https://spring.io/projects/spring-boot)
[![Next.js](https://img.shields.io/badge/Next.js-15.1.9-black.svg)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1.svg)](https://www.mysql.com/)

> 基于 **Java 21 + Spring Boot** 后端 + **Next.js 15** 前端 + **FastAPI AI Agent** 的 Web 量化交易工作台。
> 由原 PySide6 桌面端项目 ([Quantization](https://github.com/JackLiKa/Quantization.git)) 重构而来，保持原有全部功能并做性能优化、功能完善与 AI 策略优化集成。

**[功能特性](#功能一览)** • **[快速开始](#快速开始)** • **[文档](#项目导航)** • **[贡献指南](CONTRIBUTING.md)** • **[行为准则](CODE_OF_CONDUCT.md)**

---

## 目录结构

```text
Trading Workstation/
├── java/              后端：Java 21 + Spring Boot 3.3 + Spring Data JPA + Caffeine
├── next/              前端：Next.js 15 (App Router) + ECharts + shadcn/ui + Tailwind + SWR
├── agent/             AI 策略优化服务：FastAPI + LangGraph 风格优化循环 + LLM 路由
├── ingestion/         Python Baostock 数据采集脚本（由后端 sync 模块编排调用）
├── docs/              架构 / API / 数据库文档
├── .env.example       环境变量模板（后端 + 数据同步共用）
├── .gitignore
├── AGENTS.md          项目导航与开发规范（AI 协作指南）
└── README.md
```

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Java 21、Spring Boot 3.3.4、Spring Data JPA (Hibernate 6.5)、HikariCP、Caffeine、springdoc-openapi、Lombok、Spring Mail |
| 前端 | Next.js 15.1.9 (App Router, 混合渲染)、React 19、TypeScript、Tailwind CSS、shadcn/ui、ECharts、SWR |
| AI Agent | Python 3.10+、FastAPI、Uvicorn、LangGraph 风格优化循环、多模型 LLM 路由（7 供應商） |
| 数据库 | MySQL 8.0+（`stock_daily` / `index_daily` / `index_metadata` / `stock_industry` / `industry_daily` / `backtest_strategy`，A 股日线 + 540 个已验证指数 + 行業日聚合） |
| 数据同步 | Python Baostock 脚本 + `discover_indices.py` 动态发现 540 个有效指数（Java SyncService 通过 ProcessBuilder 编排） |
| 通知服务 | Spring Mail (SMTP) + Webhook（景氣度預警推送，異步發送） |

## 服务端口总览

| 服务 | 默认端口 | 配置项 | 说明 |
|------|----------|--------|------|
| Java 后端 | 8090 | `SERVER_PORT` | REST API + Swagger |
| Next.js 前端 | 3010 | `package.json` 脚本 | App Router SSR/CSR |
| Agent 服务 | 8100 | `AGENT_PORT` | AI 优化循环 + LLM 路由 |
| MySQL | 3306 | `DB_PORT` | 数据库 |

## 架构原则

- **高内聚低耦合**：后端按业务模块（`stock` / `indicator` / `dashboard` / `screener` / `backtest` / `chart` / `sync` / `system` / `preference`）组织，每个模块自包含 entity/repository/dto/service/controller；模块间通过 DTO 与服务接口协作。
- **易扩展**：新增页面/接口优先增加 `module/*` 与 `next/src/app/*` + `components/*`；指标新增只需实现 `IndicatorCalculator`。
- **易维护**：统一 `ApiResponse` 响应、全局异常处理、配置集中化（`.env` + `@ConfigurationProperties`）、前后端 DTO 类型对齐。
- **AI 集成**：Agent 服务独立部署，通过 REST API 与后端解耦，支持多 LLM 提供商自动降级。

---

## 快速开始

### 前置依赖

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| JDK | 21+（推荐 Eclipse Temurin / Microsoft OpenJDK 21） | 后端必需 |
| Node.js | 18+（推荐 20 LTS） | 前端必需 |
| Python | 3.10+ | 数据同步 + Agent 服务 |
| MySQL | 8.0+ | 数据库 |
| Maven | 3.9+ | 后端构建 |

### 1. 克隆仓库

```bash
git clone https://github.com/JackLiKa/TradingWorkstation.git
cd TradingWorkstation
```

### 2. 配置环境变量

```bash
# 后端 + 数据同步共用配置
cp .env.example .env
# 编辑 .env，填写 DB_PASSWORD 等

# Agent 服务配置
cp agent/.env.example agent/.env
# 编辑 agent/.env，填写 DEVIN_API_KEY 或 QODER_PERSONAL_ACCESS_TOKEN
```

### 3. 创建数据库

```sql
CREATE DATABASE IF NOT EXISTS a_stock_baostock DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. 数据同步（首次需导入数据）

```bash
pip install -r ingestion/requirements.txt

# 1. 发现并更新指数清单（可选，首次使用或需要扩展指数时）
python ingestion/discover_indices.py --sample --output ingestion/index_list.json

# 2. 交互式菜单同步数据
python ingestion/baostock_ingest.py
# 选择选项 11（增量更新全部：三种复权 + 指数 + 行业）
```

### 5. 启动服务

**必须按以下顺序启动**（存在依赖链）：

```
MySQL → Java 后端 (8090) → Next.js 前端 (3010)
                ↑
         Agent 服务 (8100)  ← Agent 依赖后端 REST API
```

#### Windows (PowerShell)

```powershell
# 设置 JDK 21（每次新终端需执行，或用 fix-java21-system.ps1 永久设置）
$env:JAVA_HOME = "C:\Users\<你的用户名>\.jdks\ms-21.0.9"
$env:Path = "$env:JAVA_HOME\bin;$env:Path"

# 1. 启动 Java 后端
cd java
.\start.ps1    # 或 mvn spring-boot:run

# 2. 启动 Next.js 前端（新终端）
cd next
.\start.ps1    # 或 npm run dev

# 3. 启动 Agent 服务（新终端，可选）
cd agent
.\start.ps1    # 或 python -m uvicorn app.main:app --port 8100
```

#### macOS / Linux (Bash)

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 21 2>/dev/null || echo "/usr/lib/jvm/java-21-openjdk")
export PATH="$JAVA_HOME/bin:$PATH"

# 1. 启动 Java 后端
cd java && mvn spring-boot:run

# 2. 启动 Next.js 前端（新终端）
cd next && npm install --legacy-peer-deps && npm run dev

# 3. 启动 Agent 服务（新终端，可选）
cd agent && pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

### 6. 验证启动

```bash
# 后端健康检查
curl http://localhost:8090/TradingWorkstation/api/system/health
# 期望：{"success":true,"data":{"connected":true,...}}

# 前端访问
curl -I http://localhost:3010/TradingWorkstation
# 期望：HTTP/1.1 200

# Agent 健康检查
curl http://localhost:8100/api/agent/health
# 期望：{"provider":"...","available":true,...}

# Swagger 文档
# 后端：http://localhost:8090/TradingWorkstation/swagger-ui.html
# Agent：http://localhost:8100/docs
```

---

## 功能一览

### 总览面板（Dashboard）

- 指标卡片：总记录数、股票数量、最新交易日、平均涨跌幅、最新成交额
- K 线图：缩放/平移/拖拽/十字线/提示/MA/BOLL/MACD/KDJ/成交量/历史懒加载
- 最新波动列表（涨幅/跌幅 Top 8，可点击跳转搜索）
- 运行日志面板
- 数据库连接状态实时可视化（Topbar 徽章 + 全局状态横幅）

### 选股器与回测（Screener + Backtest）

- 完整区间与信号筛选（MA/BOLL/MACD/KDJ/RSI/换手率/量比等）
- 可排序结果表 + 候选详情面板
- 回测：调仓/持有/手续费/止损/止盈/净值曲线/超额曲线/调仓明细
- 策略保存/载入/对比
- CSV 导出

### AI 策略优化（Agent）

- 六阶段 AI 优化循环：市场新闻分析 → 行业分析选股 → 市场分析 → 策略生成 → 回测反思 → Prompt 生成
- 市场分析注入 540 个指数数据，支持市场形态、市场广度（market breadth）、行业与风格轮动（rotation）综合判断
- 行業分析注入景氣度指標、資金遷移、輪動預測，輔助 AI 選擇強勢行業
- 每阶段 Judge AI 评分 + 自动重试
- 始终基于历史最优策略迭代
- 工作流图谱可视化 + 系统监控面板
- 评分趋势图 + 优化历史记录
- 模型状态卡片（可展開查看詳情、手動檢查）

### 行業分析（Industry Analysis）

獨立的 `/industry` 頁面，提供 22 個視圖、3 個分組的深度行業分析：

**即時概覽（4 個視圖）**
- 行業熱力圖（Treemap，按漲跌幅著色）
- 資金流向（Top 25 柱狀圖，億元單位）
- 漲跌家數（堆疊柱狀圖）
- 景氣度（4 維度綜合評分 + 5 級等級 + 排行表）

**歷史趨勢（4 個視圖）**
- 行業走勢（雙軸走勢 + 大盤疊加 + 新聞標記）
- 輪動信號（回溯天數切換 + 多日趨勢對比 + 領漲/滯後對比）
- 資金趨勢（多日成交額趨勢線 + 淨流入/流出摘要）
- 景氣度趨勢（多日景氣度對比 + 上升/下降排行）

**進階分析（14 個視圖）**
- 相關性矩陣（Pearson 熱力圖 + 高相關行業對 + 聚類）
- 資金遷移（桑基圖 + 流入/流出排行）
- 景氣度 vs 大盤（雙軸疊加 + 相關係數 + 解讀建議）
- 輪動預測（動量+資金+趨勢綜合評分 + 信心度 + Top 5 列表）
- 預測回測（命中率 + 超額收益走勢 + 累計命中率 + 明細表）
- AutoML 調參（15 組合搜尋 + 熱力圖 + 散點圖 + 明細表）
- 景氣度熱力圖（多日×多行業矩陣 + 色階）
- 景氣度預警（突變通知 + 等級躍遷 + 郵件/Webhook 推送）
- 景氣度週期（季節性強度排行 + 月度/星期模式 + 最佳/最差月份）
- Markov 轉移（5×5 等級轉移矩陣 + 下一日概率 + 穩態分布）
- 多模型預測（ARIMA + Holt-Winters + 線性回歸 + 共識趨勢 + 走勢圖）
- 預測回測（MAE + 方向準確率 + 等級命中率 + 超額收益）
- 輪動 Markov（3×3 轉移矩陣 + 長期領漲概率排行 + 穩態分布）

**景氣度預測模型矩陣**
- Markov 狀態轉移（等級轉換概率 + 穩態分布）
- ARIMA（AR(2) + 一階差分，捕捉自相關性）
- Holt-Winters（三重指數平滑，捕捉趨勢 + 季節性）
- 線性回歸（OLS 趨勢預測）
- 輪動預測（動量+資金+趨勢綜合評分）
- 季節性分析（月度/星期模式）
- AutoML 自動調參（最佳參數搜尋）
- 預測回測驗證（MAE + 方向準確率 + 等級命中率 + 超額收益）

**通知服務**
- 郵件推送（SMTP，景氣度預警明細）
- Webhook 推送（JSON payload，可接企業微信/釘釘/Slack）
- 異步發送，不阻塞調用方

### 数据同步（Sync）

- Baostock 日线增量/全量拉取写入 `stock_daily` 与 `index_daily`
- `discover_indices.py` 从 Baostock `query_all_stock` 动态发现并验证指数代码，当前清单含 540 个有效指数（综合 / 规模 / 行业 / 策略 / 成长 / 价值 / 主题 / 基金 / 债券）
- 指数元数据自动同步至 `index_metadata` 表
- 三种复权（前复权/后复权/不复权）+ 指数数据 + 行业分类
- 行業日聚合數據自動生成（`JOIN stock_daily × stock_industry` 按 `(date, industry)` 聚合寫入 `industry_daily`）
- 前端同步进度可视化 + 取消功能

### 系统设置（Settings）

- 数据库配置校验与持久化
- 用户偏好（默认复权/默认查询条数/指标参数等）

---

## 项目导航

详细的模块说明、启动流程、常见问题请参阅 [`AGENTS.md`](./AGENTS.md)。

架构设计、API 文档、数据库文档请参阅 [`docs/`](./docs/)：

- [`docs/architecture.md`](./docs/architecture.md) — 系统架构与模块设计
- [`docs/api.md`](./docs/api.md) — REST API 接口文档
- [`docs/database.md`](./docs/database.md) — 数据库表结构与索引设计

各子模块 README：

- [`java/README.md`](./java/README.md) — 后端模块说明
- [`next/README.md`](./next/README.md) — 前端模块说明
- [`agent/README.md`](./agent/README.md) — AI Agent 服务说明

## 缓存说明

- **后端 Caffeine**：`dashboardSummary`（60s TTL）、`dashboardMetrics`（30s TTL）、`indexMetadata` / `marketBreadth` / `rotationSignal` / `sectorPerformance`（30s TTL）、`industryDailyCache`（行業景氣度/輪動預測/Markov/預測/回測等分析結果，5 分鐘 TTL）。数据同步后等待 TTL 过期或重启后端。
- **前端 SWR**：默认 `revalidateOnFocus`，可通过 `mutate()` 手动刷新。行業分析視圖 `dedupingInterval` 設為 5 分鐘，避免頻繁重複請求。

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| `Port 8090 was already in use` | 终止占用进程：`Stop-Process -Id (Get-NetTCPConnection -LocalPort 8090).OwningProcess -Force` |
| 前端显示"数据库未连接" | 检查后端是否启动、`.env` 中 `DB_PASSWORD` 是否正确 |
| 回测超时 | 缩短回测日期范围，或检查 `next.config.js` 中 `proxyTimeout` 配置 |
| Baostock 登录超时 | 脚本已实现自动重新登录，无需人工干预 |
| `NoClassDefFoundError` | Maven 本地仓库路径含非 ASCII 字符，改为纯 ASCII 路径 |

## 致谢

- [Baostock](http://baostock.com/) — A 股历史数据源
- [Spring Boot](https://spring.io/projects/spring-boot) — 后端框架
- [Next.js](https://nextjs.org/) — 前端框架
- [ECharts](https://echarts.apache.org/) — 图表库
- [shadcn/ui](https://ui.shadcn.com/) — UI 组件设计
- [FastAPI](https://fastapi.tiangolo.com/) — Agent 服务框架
- 原 [Quantization](https://github.com/JackLiKa/Quantization.git) PySide6 桌面端项目

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JackLiKa/TradingWorkstation&type=Date)](https://star-history.com/#JackLiKa/TradingWorkstation&Date)

## License

本项目基于 [MIT License](LICENSE) 开源，仅供学习和个人使用。

## 相关文档

- [贡献指南](CONTRIBUTING.md)
- [行为准则](CODE_OF_CONDUCT.md)
- [安全政策](SECURITY.md)
- [项目导航与开发规范](AGENTS.md)
