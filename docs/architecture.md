# 架构概览

## 整体分层

```
┌──────────────────────────────────────────┐
│  next/  Next.js 前端 (SSR+CSR)            │  ECharts / shadcn-ui / SWR
│  basePath: /TradingWorkstation            │
└──────────────┬──────────────┬────────────┘
               │ REST / JSON   │ REST / JSON (Agent 無前綴)
┌──────────────▼──────────────┐  ┌─────────▼──────────────┐
│  java/  Spring Boot 后端     │  │  agent/  FastAPI Agent  │
│  context-path: /TradingWorkstation │  │  端口 8100          │
│  端口 8090                   │  │  AI 優化循環 + 評委     │
│  ┌──────────────────────┐   │  │  + 監控 + 6 AI 節點     │
│  │  controller (REST)   │   │  └─────────┬──────────────┘
│  │  service (业务+指标)  │   │            │ 調用後端 API
│  │  repository (JPA)    │   │←───────────┘
│  │  indicator 引擎      │   │
│  └──────────────────────┘   │
└──────────────┬──────────────┘
               │
        ┌──────▼──────┐
        │   MySQL      │  stock_daily / stock_industry / index_daily / index_metadata
        └──────────────┘
               ▲
        ┌──────┴──────┐
        │ ingestion/   │  Python Baostock (SyncService 编排)
        └─────────────┘
```

## 后端模块（com.quantization）

| 模块 | 职责 |
|------|------|
| `config` | 配置类（缓存、OpenAPI、Web、CORS）与 `@ConfigurationProperties` |
| `common` | 跨切面：统一响应 `ApiResponse`/`PageResponse`、全局异常、工具类 |
| `module.stock` | `stock_daily`/`stock_industry` 实体、仓储、行情查询、模糊搜索、行业分类 |
| `module.indicator` | 指标引擎：MA/EMA/MACD/KDJ/RSI/BOLL/量比/区间收益/评分 |
| `module.dashboard` | 总览面板：汇总指标、最新波动、K 线初始加载 |
| `module.screener` | 选股器：条件筛选、评分排序 |
| `module.backtest` | 回测：调仓回放、净值/超额曲线、统计（夏普比率、最大回撤） |
| `module.chart` | K 线按需加载历史（分批拉取更早数据） |
| `module.sync` | 数据同步：编排 Python Baostock 拉取并写入 |
| `module.system` | 数据库配置校验、健康检查 |
| `module.preference` | 用户偏好持久化 |

### 依赖方向

```
controller → service → repository / indicator引擎
            ↘ common.api / common.util
模块间不直接互调仓储，通过 service / DTO 协作。
```

## Agent 服務模塊（agent/app）

| 模塊 | 職責 |
|------|------|
| `main.py` | FastAPI 入口，APScheduler 定時模型檢查 |
| `core/config.py` | Pydantic settings，從 agent/.env 加載 |
| `core/llm_client.py` | 統一 LLM 接口（Qoder lite → Devin GLM-5.2 → 降級） |
| `core/logging.py` | 日誌配置 |
| `agents/optimizer.py` | 優化循環編排（6 AI 節點串聯 + 評委 + 回測） |
| `agents/state.py` | 優化狀態、迭代結果、階段結果數據模型 |
| `agents/scoring.py` | 綜合評分計算 |
| `agents/judge.py` | 評委 AI（格式檢查 + LLM 評分 + 重試策略） |
| `agents/monitor.py` | 節點生命周期監控 + 異常檢測（AOP） |
| `agents/monitor_ai.py` | 監測 AI（LLM 分析系統健康 + 建議） |
| `agents/stages/base.py` | AI 節點基類（pre/execute/judge/retry/post 生命週期） |
| `agents/stages/market_news.py` | AI 0：行情新聞分析（實時指數 + 10日市場廣度/輪動 + 市場情緒） |
| `agents/stages/industry_analysis.py` | AI 0.5：行業篩選（利好行業 + 候選股票） |
| `agents/stages/market_analysis.py` | AI 1：行情分析（趨勢判斷 + 廣度/輪動 + 波動率 + 策略類型） |
| `agents/stages/strategy_generation.py` | AI 2：策略生成（選股條件 JSON） |
| `agents/stages/backtest_reflection.py` | AI 3：回測反思（績效分析 + 改進建議） |
| `agents/stages/prompt_generation.py` | AI 4：提示詞生成（下一輪優化方向） |
| `services/backend_client.py` | 後端 API 客戶端（回測、選股、行業數據） |
| `services/market_data_client.py` | 實時行情數據客戶端（新浪財經 API） |
| `services/model_checker.py` | 模型可用性定時檢查 |
| `api/routes.py` | FastAPI 路由層 |

### AI 優化工作流

```
f0（歷史最優策略）
  → AI 0 行情新聞 → 評委
  → AI 0.5 行業篩選 → 評委
  → AI 1 行情分析 → 評委
  → AI 2 策略生成 → 評委
  → 回測
  → AI 3 回測反思 → 評委
  → AI 4 提示詞生成 → 評委
  → f1（新策略，持久化到數據庫）
  → 下一輪...
```

## 前端结构（next/src）

| 目录 | 职责 |
|------|------|
| `app/` | App Router 路由：dashboard / screener / agent / sync / settings |
| `components/layout` | Sidebar / Topbar / LoadingOverlay |
| `components/ui` | shadcn/ui 基础组件 |
| `components/dashboard` | 指标卡 / 波动列表 / 工具栏 / 日志 |
| `components/chart` | ECharts K 线主图 / 副图指标 / 回测曲线 / 指标设置 |
| `components/screener` | 筛选面板 / 信号面板 / 结果表 / 详情 / 规则预览 |
| `components/backtest` | 回测结果 / 调仓明细表 |
| `components/agent` | Agent 狀態面板 / 工作流圖譜 / 監控面板 / 迭代卡片 / 評分趨勢 |
| `components/sync` / `components/settings` | 同步面板 / 数据库配置表单 |
| `components/common` | DataTable / StatusBadge / CopyButton |
| `lib/api` | fetch 封装、与后端对齐的 TS 类型、各端点 |
| `lib/hooks` | SWR 数据 hooks |
| `lib/store` | zustand 客户端状态（筛选条件、偏好） |
| `lib/indicators` | 前端轻量指标计算（图表叠加，与后端公式对齐） |
| `lib/format` | 数字 / 货币 / 百分比格式化 |

## 关键设计决策

1. **路由前綴**：後端 `server.servlet.context-path=/TradingWorkstation`，前端 `next.config.js basePath='/TradingWorkstation'`，Agent 不加前綴（獨立服務）。
2. **指标计算位置**：在 Java 服务层用与原 Python 完全相同的公式计算，保证行为一致；性能通过数据访问优化与 Caffeine 缓存实现。
3. **数据同步**：Baostock 无 Java SDK，后端 `SyncService` 通过 `ProcessBuilder` 编排 `ingestion/baostock_ingest.py`，结果写入 `stock_daily`（`ON DUPLICATE KEY UPDATE`）。
4. **统一响应**：所有后端接口返回 `ApiResponse<T>`，含 `success/code/message/data`；分页用 `PageResponse<T>`。
5. **配置**：`.env` → Spring `application.yml` 占位符 → `@ConfigurationProperties` 类型安全绑定；密钥不入库。
6. **前后端类型对齐**：`lib/api/types.ts` 与后端 DTO 字段一一对应，命名 camelCase。
7. **AI 節點模塊化**：每個 AI 節點繼承 `BaseStage`，有獨立的 prompt 和 execute 邏輯；評委通過生命週期鉤子自動介入；監控通過 AOP 記錄節點事件。
8. **LLM 降級策略**：Qoder lite（免費）→ Devin GLM-5.2 High（免費）→ 關閉 AI 優化。
