# API 概览

## 路由前綴

所有後端 API 都帶 `/TradingWorkstation` 前綴。

- Base URL: `http://localhost:8090/TradingWorkstation/api`
- Swagger: `http://localhost:8090/TradingWorkstation/swagger-ui.html`
- 健康檢查: `http://localhost:8090/TradingWorkstation/actuator/health`

统一响应：`{ "success": bool, "code": string, "message": string, "data": T }`

## 总览 dashboard

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/dashboard` | 加载总览（汇总指标 + 表格 + K 线初始 + 波动 + 日志），query: code, adjustflag, startDate, endDate, limit |
| GET | `/dashboard/summary` | 仅汇总指标（Caffeine 缓存，TTL 60s） |

## 行情 stock

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/stock/search` | 日线表格查询（分页 + 模糊搜索），query: code, adjustflag, startDate, endDate, page, limit |
| GET | `/stock/movers` | 最新波动（涨幅/跌幅榜），query: limit |
| GET | `/stock/suggest` | 股票代码模糊建议（下拉框），query: q, limit |
| GET | `/stock/industries` | 行业分类查询，query: code, industry, limit |
| GET | `/stock/industries/list` | 所有不同行业名称列表 |
| GET | `/stock/index-history` | 指數最近 N 日歷史，query: code, days（默認 10） |
| POST | `/stock/index-history/batch` | 批量指數最近 N 日歷史，body: `{codes, days}` |
| GET | `/stock/index-list` | 指數元數據列表（10 大類別 ~80 個指數），query: categoryCode（可選） |
| GET | `/stock/market-breadth` | 市場廣度分析（綜合/規模/風格/行業），query: days（默認 10） |
| GET | `/stock/rotation` | 輪動信號分析（行業/風格輪動），query: days（默認 10） |
| GET | `/stock/sector-performance` | 多日板塊表現，query: days（默認 10） |
| GET | `/stock/industry-daily` | 行業日聚合數據，query: tradeDate（可選，默認最新交易日） |
| GET | `/stock/industry-daily/range` | 指定行業區間聚合，query: industry, start, end |
| GET | `/stock/industry-correlation` | 行業相關性矩陣，query: days（默認 30） |
| GET | `/stock/industry-capital-migration` | 行業資金遷移分析，query: days（默認 5） |
| GET | `/stock/industry-prosperity` | 行業景氣度分析（4 維度綜合評分 + 5 級等級） |
| GET | `/stock/industry-prosperity/trend` | 景氣度歷史趨勢，query: days（默認 10） |
| GET | `/stock/industry-prosperity/benchmark` | 景氣度 vs 大盤疊加，query: days（默認 60） |
| GET | `/stock/industry-prosperity/heatmap` | 景氣度熱力圖矩陣，query: days（默認 10） |
| GET | `/stock/industry-prosperity/alerts` | 景氣度異常預警，query: threshold（默認 10）, notify（默認 false） |
| GET | `/stock/industry-prosperity/seasonality` | 景氣度週期性分析（季節性模式），query: months（默認 12） |
| GET | `/stock/industry-prosperity/markov` | 景氣度 Markov 狀態轉移模型，query: months（默認 12） |
| GET | `/stock/industry-prosperity/forecast` | 景氣度多模型預測（ARIMA+Holt-Winters+線性回歸），query: months, forecastDays |
| GET | `/stock/industry-prosperity/forecast/backtest` | 景氣度預測回測驗證，query: months, forecastDays, backtestDays |
| GET | `/stock/rotation-prediction` | 輪動預測（動量+資金+趨勢），query: lookbackDays（默認 20） |
| GET | `/stock/rotation-prediction/backtest` | 輪動預測回測，query: lookbackDays, forwardDays, backtestDays |
| GET | `/stock/rotation-prediction/automl` | 輪動預測 AutoML 自動調參，query: backtestDays（默認 90） |
| GET | `/stock/rotation-markov` | 行業輪動 Markov 模型（領漲轉換概率），query: lookbackDays（默認 30） |

## K 线 chart

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/chart/candlestick` | K 线初始批次，query: code, adjustflag, startDate, endDate, batchSize |
| GET | `/chart/candlestick/older` | 更早历史（分页拉取），query: code, adjustflag, beforeDate, batchSize |

## 选股 screener

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/screener/run` | 运行选股筛选，body: ScreenerCriteria，返回 ScreenerResult |

## 回测 backtest

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/backtest/run` | 运行回测，body: { criteria, config }，返回 BacktestResult |
| GET | `/backtest/strategies` | 所有已保存策略列表 |
| GET | `/backtest/strategies/{id}` | 单个策略详情 |

## 指标 indicator

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/indicator/compute` | 计算技术指标，body: { records, config }，返回各指标序列 |

## 数据同步 sync

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/sync/run` | 触发同步任务，body: { mode, adjustflags, syncIndex, syncIndustry } |
| GET | `/sync/status` | 当前任务状态与进度 |
| POST | `/sync/cancel` | 取消正在运行的同步任务 |

## 系统 system

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/system/health` | 数据库连接 + 表结构校验 |
| PUT | `/system/database` | 更新数据库配置（校验后写 .env） |
| GET | `/system/notification/test` | 通知服務測試（郵件/Webhook） |

## 偏好 preference

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/preference` | 读取用户偏好 |
| PUT | `/preference` | 保存用户偏好 |

## Agent 服务 API（端口 8100，无前綴）

Agent 是獨立的 AI 優化服務，API 不帶 `/TradingWorkstation` 前綴。

- Base URL: `http://localhost:8100/api/agent`
- Swagger: `http://localhost:8100/docs`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康檢查 + 模型狀態 + 後端連通性 |
| POST | `/start` | 启动 AI 優化循環 |
| POST | `/stop` | 停止優化循環 |
| GET | `/status` | 當前優化狀態（含實時階段結果） |
| GET | `/history?limit=N` | 優化歷史記錄 |
| GET | `/history/{iteration}` | 特定輪次詳情 |
| GET | `/criteria` | 當前選股條件 |
| POST | `/criteria` | 手動更新選股條件 |
| POST | `/model/check` | 手動觸發模型可用性檢查 |
| GET | `/monitor` | 監控狀態（節點事件 + 告警 + 統計） |
| GET | `/monitor/analyze` | 監測 AI 診斷系統健康 |
| POST | `/monitor/alerts/{id}/resolve` | 標記告警為已解決 |

> 详细字段见 `java/.../module/*/dto` 与 `next/src/lib/api/types.ts`，二者一一对应。
