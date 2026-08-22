# REST API 參考（API Reference）

> 覆蓋 Java 後端全部 52 個端點 + Agent 服務 22 個端點。權威來源是 Swagger（後端 `/TradingWorkstation/swagger-ui.html`、agent `:8100/docs`），本文檔提供帶示例的速查。
> 最後校準日期：2026-08-22（基於代碼實讀，覆蓋 Phase 4 + Phase 5 全部變更）。

---

## 基礎信息

| 項 | 值 |
|----|-----|
| 後端 Base URL | `http://localhost:8090/TradingWorkstation/api` |
| 後端 Swagger | `http://localhost:8090/TradingWorkstation/swagger-ui.html` |
| 後端 OpenAPI JSON | `http://localhost:8090/TradingWorkstation/v3/api-docs` |
| Agent Base URL | `http://localhost:8100/api/agent` |
| Agent Swagger | `http://localhost:8100/docs` |
| 前端訪問路徑 | 瀏覽器 → `http://localhost:3010/TradingWorkstation/api/*`（next rewrites 反代到後端） |

---

## 通用約定

### 統一響應信封（後端）

```json
{ "success": true, "code": "OK", "message": "...", "data": { } }
```

失敗時 `success=false`，`code ∈ {BAD_REQUEST, VALIDATION_ERROR, NOT_FOUND, DB_ERROR, SYNC_ERROR, INTERNAL_ERROR}`。

- 日期格式一律 `yyyy-MM-dd`；時區 Asia/Shanghai
- null 字段不序列化（`NON_NULL`，`application.yml:34`）
- **無認證**：所有端點開放（僅適合可信網絡，見 `architecture.md §9`）

### adjustflag 復權約定（多數行情端點共用）

| 值 | 含義 |
|----|------|
| 1 | 後復權 |
| 2 | 前復權 |
| 3 | 不復權（**默認**） |

---

## 1. stock（/api/stock，26 端點）

### 1.1 行情查詢

| 方法 | 路徑 | 參數（默認） | 出參 |
|------|------|-------------|------|
| GET | /summary ⚠️已棄用 | — | SummaryMetricsDto（請改用 `/api/dashboard/summary`） |
| GET | /search | code, adjustflag=3, startDate, endDate, limit=50, offset=0 | SearchResultDto（分頁） |
| GET | /movers | limit=8 | HotSymbolDto[]（最新交易日 \|漲跌幅\| 榜） |
| GET | /suggest | q（代碼或名稱片段）, limit=10 | StockSuggestionDto[] |

**示例**：

```bash
curl "http://localhost:8090/TradingWorkstation/api/stock/search?code=600000&adjustflag=3&limit=20"
```

`SummaryMetricsDto`：`{totalRecords, totalSymbols, earliestTradeDate, latestTradeDate, averagePctChange, latestTurnover}`

### 1.2 行業分類與聚合

| 方法 | 路徑 | 參數 | 說明 |
|------|------|------|------|
| GET | /industries | code, industry | 個股行業分類查詢 |
| GET | /industries/list | — | 全部不同行業名 |
| GET | /industry-daily | tradeDate（空=最新日） | 單日全行業聚合 |
| GET | /industry-daily/range | industry, start, end | 單行業區間 |
| GET | /industry-daily/all-range | start, end | 全行業區間（相關性矩陣用） |

`IndustryDailyDto`：`{tradeDate, industry, stockCount, avgPctChg, totalAmount, totalVolume, avgTurn, risingCount, fallingCount, avgClose, maxClose, minClose}`

### 1.3 行業景氣度

| 方法 | 路徑 | 參數（默認/範圍） | 出參 |
|------|------|-------------------|------|
| GET | /industry-prosperity | tradeDate | IndustryProsperityDto[] |
| GET | /industry-prosperity/range | start, end, topN=15 | IndustryProsperityDto[] |
| GET | /industry-prosperity/alerts | threshold=10.0, notify=false | ProsperityAlertDto |
| GET | /industry-prosperity/seasonality | months=12 (1-60) | ProsperitySeasonalityDto |
| GET | /industry-prosperity/markov | months=12 (1-36) | ProsperityMarkovDto |
| GET | /industry-prosperity/forecast | months=6 (1-24), forecastDays=5 (1-20) | ProsperityForecastDto |
| GET | /industry-prosperity/forecast/backtest | months=6, forecastDays=5, backtestDays=60 | ProsperityForecastBacktestDto |

**景氣度公式**（`IndustryService.java:92-177`）：

```
景氣度 = 動量 0.35 + 資金 0.25 + 活躍 0.20 + 廣度 0.20
（當日橫截面 min-max 歸一到 0-100）
```

等級：≥80 繁榮 / ≥65 景氣 / ≥50 平穩 / ≥35 低迷 / 其餘衰退。

> ⚠️ **方法論警告 P4-11 — 橫截面歸一化語義**：分數是**當日相對排名**，非絕對景氣。全市場齊跌時仍有行業得 80+ 分「繁榮」。跨日比較需謹慎解讀。

> ⚠️ **預警觸發語義**：`alerts?notify=true` 才會觸發郵件/Webhook 推送。已加 `ProsperityAlertScheduler`（P4-8），可配置 `ALERT_SCHEDULER_ENABLED=true` + cron 定時檢查，**預設關閉**保持向後兼容。

### 1.4 輪動預測

| 方法 | 路徑 | 參數（默認） | 出參 |
|------|------|-------------|------|
| GET | /rotation-prediction | lookbackDays=20 | RotationPredictionDto |
| GET | /rotation-prediction/backtest | lookbackDays=20, forwardDays=5, backtestDays=90 | RotationBacktestDto |
| GET | /rotation-prediction/automl | backtestDays=90 | RotationAutoMlDto（15 組合網格搜索） |
| GET | /rotation-markov | lookbackDays=30 (5-180) | RotationMarkovDto |
| GET | /rotation | days=10 | RotationSignalDto |

> ⚠️ **方法論警告 P4-14 — "AutoML" 命名**：實為 15 組合窮舉網格搜索（lookback×forward = 5×3），無貝葉斯/隨機搜索。已改為 tune/eval 切分防 in-sample 過擬合——將 backtestDays 前 2/3 用於調參、後 1/3 用於評估（`ForecastService.java:475-478`）。但搜索空間有限，泛化能力仍受限。

> ⚠️ **方法論警告 P4-3 — 集成權重**：固定 0.35/0.35/0.30（ARIMA/HW/LR），回測端點計算最優逆 MAE 權重供參考但**不自動回饋**（`ForecastService.java:38`）。

### 1.5 指數與市場

| 方法 | 路徑 | 參數 | 出參 |
|------|------|------|------|
| GET | /index-history | code, days=10 | IndexDailyDto[] |
| POST | /index-history/batch | `{codes: string[], days: int}` | Map\<code, IndexDailyDto[]\> |
| GET | /sector-performance | days=10 | SectorPerformanceDto[]（含窗口函數選出的領漲股） |
| GET | /market-breadth | days=10 | MarketBreadthDto |
| GET | /index-list | categoryCode（可空） | IndexMetadataDto[]（10 大類別） |

---

## 2. industry（/api/stock 行業端點，由 IndustryService 提供）

> 行業模塊的端點掛在 `/api/stock` 前綴下（見 §1.2-1.3），由 `IndustryService` 提供實現。

**核心方法**（`IndustryService.java`）：

| 方法 | 職責 | 緩存 |
|------|------|------|
| `industryDailyByDate()` | 單日全行業聚合 | INDUSTRY_DAILY_CACHE |
| `industryDailyRange()` | 單行業區間 | INDUSTRY_DAILY_CACHE |
| `allIndustryDailyRange()` | 全行業區間（相關性矩陣） | INDUSTRY_DAILY_CACHE |
| `industryProsperity()` | 行業景氣度計算 | INDUSTRY_DAILY_CACHE |
| `industryProsperityRange()` | 景氣度歷史趨勢 | INDUSTRY_DAILY_CACHE |
| `prosperityAlerts()` | 景氣度異常預警 | INDUSTRY_DAILY_CACHE |

---

## 3. forecast（/api/stock 預測端點，由 ForecastService 提供）

> 預測模塊的端點掛在 `/api/stock` 前綴下（見 §1.3-1.4），由 `ForecastService`（1,763 行）提供實現。

**核心方法**（`ForecastService.java`）：

| 方法 | 職責 | 緩存 |
|------|------|------|
| `prosperitySeasonality()` | 季節性分析 | FORECAST_CACHE |
| `prosperityMarkov()` | Markov 狀態轉移模型 | FORECAST_CACHE |
| `prosperityForecast()` | 三模型預測（ARIMA+HW+LR） | FORECAST_CACHE |
| `prosperityForecastBacktest()` | 預測回測驗證 | FORECAST_CACHE |
| `predictRotation()` | 輪動預測 | ROTATION_CACHE |
| `backtestRotationPrediction()` | 輪動預測回測 | ROTATION_CACHE |
| `autoTuneRotationPrediction()` | AutoML 調參 | ROTATION_CACHE |
| `rotationMarkov()` | 輪動 Markov | ROTATION_CACHE |

> ⚠️ **方法論警告 P4-13 — "ARIMA" 命名**：實為 ARI(2,1) 無 MA 項、無定階（無 AIC/BIC）、無平穩性檢驗（`ForecastService.java:1448`）。命名大於實質——非完整 Box-Jenkins 方法論。

> ⚠️ **方法論警告 P4-9 — HW 季節週期**：硬編碼 `HW_SEASON_LENGTH=5`（交易週，`ForecastService.java:35`）。月度/季度季節性（20/60 交易日）被完全忽略。

> ⚠️ **方法論警告 P4-4 — Markov 一階假設**：景氣度等級轉移假設只依賴前一狀態，無法捕捉多步記憶的週期模式。

---

## 4. indicator（/api/indicator，1 端點）

| 方法 | 路徑 | 入參 | 出參 |
|------|------|------|------|
| POST | /compute | `{records: StockDaily[], config: IndicatorConfigDto}` | IndicatorSeriesDto |

**IndicatorConfigDto**（全部可空，非 null 字段覆蓋默認值，`IndicatorController.java:46-62`）：

```json
{
  "showMa": true, "maPeriods": [5, 10, 20],
  "showBoll": false, "bollPeriod": 20, "bollStd": 2.0,
  "showMacd": false, "macdFastPeriod": 12, "macdSlowPeriod": 26, "macdSignalPeriod": 9,
  "showKdj": false, "kdjPeriod": 9, "kdjKSmoothing": 3, "kdjDSmoothing": 3
}
```

**IndicatorSeriesDto**：`{maSeries: Map<int, double[]>, bollUpper/middle/lower, macd/dea/dif, k/d/j, rsi}`

> ✅ 已修復：請求 DTO 中非 null 字段會覆蓋默認值（`mergeConfig`），前端可自定義 MA/BOLL/MACD/KDJ 參數。

---

## 5. screener（/api/screener，1 端點）

| 方法 | 路徑 | 入參 | 出參 |
|------|------|------|------|
| POST | /run | ScreenerCriteriaDto | ScreenerResultDto |

**ScreenerCriteriaDto**（49 字段全部可空，服務端填默認值，條件間**隱式 AND**）：

- **基礎區間**：min/maxClose、min/maxPctChange、min/maxTurn、min/maxAmplitude、minVolume、minAmount、min/maxVolumeRatio
- **動量區間**：min/maxReturn20、min/maxReturn60、min/maxReturn120
- **技術指標區間**：min/maxRsi14、min/maxKValue、min/maxDValue、min/maxJValue、min/maxMacdHist、min/maxBollWidth、min/maxBollPercentB
- **均線關係**（Boolean）：priceAboveMa5/20/60、ma5AboveMa20、ma20AboveMa60
- **交叉信號**：macdCrossSignal / kdjCrossSignal ∈ {golden, death, any}，配 macdCrossWithinDays / kdjCrossWithinDays（0=僅當日）
- **其他**：bollPosition、excludeSt=true、industries[]、maxResults=100、sortBy=score、asOfDate=今天、adjustflag=3

> ✅ **Phase 5 嵌套視圖**：保留 49 個扁平字段維持序列化格式不變，同時提供按域分組的嵌套子記錄視圖訪問器（`ScreenerCriteriaDto.java:66-156`）：`priceFilter()` / `pctChangeFilter()` / `turnoverFilter()` / `volumeFilter()` / `momentumFilter()` / `technicalFilter()` / `maFilter()` / `crossFilter()` / `bollFilter()`。嵌套視圖為只讀派生視圖，不參與 Jackson 序列化。

**示例**：

```bash
curl -X POST http://localhost:8090/TradingWorkstation/api/screener/run \
  -H "Content-Type: application/json" \
  -d '{"minPctChange":2,"minTurn":3,"macdCrossSignal":"golden","macdCrossWithinDays":3,"excludeSt":true,"maxResults":50}'
```

**出參**：`{criteria(回顯歸一化後), screenDate, scannedSymbols, matchedSymbols, candidates: ScreenedStockDto[](含全指標快照), summaryLines}`

⚠️ **語義限制**：條件間只有 AND，無法表達 OR/嵌套。

---

## 6. backtest（/api/backtest，7 端點）

| 方法 | 路徑 | 入參 | 出參 |
|------|------|------|------|
| POST | /run | BacktestRequestDto | BacktestResultDto |
| POST | /run-and-save | BacktestRequestDto | BacktestResultDto（與 /run 等價，runBacktest 已內置自動落庫） |
| POST | /strategies | SaveStrategyDto | SavedStrategyDetailDto |
| GET | /strategies?source= | — | SavedStrategySummaryDto[] |
| GET | /strategies/{id} | — | SavedStrategyDetailDto |
| GET | /recent?limit=20 | — | SavedStrategySummaryDto[]（最近回測記錄） |
| DELETE | /strategies/{id} | — | — |

**BacktestRequestDto** = `{criteria: ScreenerCriteriaDto, config: BacktestConfigDto}`

**BacktestConfigDto**（`BacktestConfigDto.java`）：

```json
{
  "startDate": "2025-01-01", "endDate": "2025-06-30",
  "rebalanceInterval": 5, "holdingPeriod": 10, "maxPositions": 10,
  "initialCapital": 1000000, "commissionBps": 3,
  "stopLossPct": null, "takeProfitPct": null,
  "riskFreeRate": 0.02,
  "slippageBps": 0
}
```

| 字段 | 默認 | 說明 |
|------|------|------|
| riskFreeRate | 0.02 | 無風險年化利率，用於夏普比率計算（`BacktestConfigDto.java:34`） |
| slippageBps | 0 | 滑點（基點），買入價上浮、賣出價下浮（`BacktestConfigDto.java:36`） |

`criteria.adjustflag` 可為 null（服務端默認 3，`BacktestService.java:97`）。

**BacktestResultDto**：`{config, strategyCurve/benchmarkCurve/excessCurve: EquityPoint[], rebalances: RebalanceEvent[], statistics, logLines}`

**BacktestStatistics**：`{totalReturn, annualReturn, benchmarkReturn, excessReturn, maxDrawdown, sharpe, rebalanceCount, totalTrades}`（單位 %，sharpe 無量綱）

> ⚠️ **方法論警告 — 回測滑點/漲跌停假設**：
> - **滑點**：買入價 = close × (1 + slippageRate)，賣出價 = close × (1 - slippageRate)（`BacktestService.java:89`）
> - **漲跌停約束**：調倉選股跳過當日漲停（pctChg ≥ 9.9，買不進）/ 跌停（pctChg ≤ -9.9）；止損賣出遇跌停延後到下一交易日（`BacktestService.java:60`）
> - **夏普減無風險利率**：`sharpe = (mean - rf/252) / std × √252`（`BacktestService.java:379-380`）
> - **結果自動落庫**：`runBacktest` 結果自動落庫 source=auto（best-effort，失敗不影響結果返回，`BacktestService.java:412-432`）
> - 完整假設聲明見 `docs/BACKTEST_ENGINE.md §6`

---

## 7. chart（/api/chart，2 端點）

| 方法 | 路徑 | 參數 | 說明 |
|------|------|------|------|
| GET | /candlestick | code, adjustflag=3, startDate, endDate, + IndicatorConfigDto（可選） | 初始批次 + 指標序列 + hasMore |
| GET | /candlestick/older | + beforeDate（遊標，必填）+ IndicatorConfigDto（可選） | 向更早翻頁 |

- 批次大小由 `app.chart.batch-size` 配置（默認 500，`AppProperties.java:81`）
- 支持透傳指標配置參數（showMa/showBoll/showMacd/showKdj 及各週期參數，`ChartController.java:48,71`）
- 前端 `CandlestickChart` 滾動到左端觸發 older 拉取

---

## 8. dashboard（/api/dashboard，2 端點）

| 方法 | 路徑 | 參數 | 出參 |
|------|------|------|------|
| GET | / | code, adjustflag, startDate, endDate, limit | DashboardSnapshotDto（聚合 metrics+records+chart+movers+狀態） |
| GET | /summary | — | SummaryMetricsDto（緩存 60s） |

- Dashboard 聚合經 `asyncExecutor`（8 線程）部分並行
- `/summary` 直接轉調 `stockService.summaryMetrics()`，非重複實現

---

## 9. sync（/api/sync，3 端點）

| 方法 | 路徑 | 入參 | 說明 |
|------|------|------|------|
| POST | /run | SyncRequestDto | 啟動同步（同時僅允許一個任務） |
| GET | /status | — | SyncStatusDto |
| POST | /cancel | — | 銷毀子進程 |

**SyncRequestDto**：`{mode: incremental|range, adjustflags: "1,2,3", start, end, codes, syncIndex, syncIndustry}`

**示例**：

```bash
curl -X POST http://localhost:8090/TradingWorkstation/api/sync/run \
  -H "Content-Type: application/json" \
  -d '{"mode":"incremental","adjustflags":"1,2,3","syncIndex":true,"syncIndustry":true}'
```

**SyncStatusDto**：`{state: IDLE|RUNNING|SUCCESS|FAILED|CANCELLED, progress, message, written, startedAt, finishedAt, error}`（progress 目前僅 0/50/100 三檔）

---

## 10. system（/api/system，4 端點）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | /health | `{connected, schemaValid, issues[]}` — 校驗 stock_daily 表/列/唯一索引 |
| GET | /database | 當前 DB 配置（不含密碼） |
| PUT | /database | 僅校驗輸入，不自動寫 .env；需手動修改 .env 後重啟 ⚠️ 容器部署下無效 |
| GET | /notification/test | 按當前配置發測試郵件/Webhook |

> ⚠️ **方法論警告 P4-8 — 預警調度器**：已加 `ProsperityAlertScheduler`，可配置 `ALERT_SCHEDULER_ENABLED=true` + cron 定時檢查景氣度預警並自動推送郵件/Webhook。**預設關閉**——啟用前需確認 SMTP/Webhook 配置正確（先用 `/notification/test` 驗證），否則定時觸發的告警會靜默失敗（通知服務無重試，失敗僅 warn）。

---

## 11. preference（/api/preference，2 端點）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | / | 讀 UserPreferenceDto（DB 無記錄返回空默認） |
| PUT | / | 全量覆蓋保存 |

**UserPreferenceDto**：`{defaultAdjustflag, defaultLimit, defaultLookbackDays, watchlist, screenerPresets: Map, indicatorConfig, defaultSortBy}`

> ✅ **Phase 5 入庫**：主存儲為 MySQL `user_preference` 表（`PreferenceEntity`），DB 異常時自動降級到文件存儲（`PreferenceService.java:56-78`）。`userId` 默認 `"default"`，未來可擴展多用戶。

---

## 12. aicalllog（/api/aicalllog，6 端點）

| 方法 | 路徑 | 參數 | 說明 |
|------|------|------|------|
| POST | /log | AiCallLogRequest | agent 回寫調用日誌 |
| GET | / | page=0, size=20 | 分頁查詢全部 |
| GET | /stage/{stageName} | page, size | 按階段分頁 |
| GET | /iteration/{iteration} | — | 某迭代完整調用鏈 |
| GET | /recent | limit=10 | 最近日誌 |
| GET | /score-trend | — | `{stageTrends, iterationTrends, stages, maxIteration}` |

**score-trend 返回**（供前端 `/agent-dashboard` 繪圖）：

```json
{
  "stageTrends": [{"iteration": 1, "stageName": "...", "avgScore": 75.0, "maxScore": 90, "minScore": 60}],
  "iterationTrends": [{"iteration": 1, "avgScore": 75.0, "callCount": 7}],
  "stages": ["market_news", "industry_analysis", "..."],
  "maxIteration": 10
}
```

> ✅ **Phase 5 清理調度器**：`AiCallLogCleanupScheduler`（預設關閉），`AICALLLOG_CLEANUP_ENABLED=true` 啟用，保留天數 `AICALLLOG_RETENTION_DAYS=90`，cron `AICALLLOG_CLEANUP_CRON`（默認每天凌晨 2:00，`AiCallLogCleanupScheduler.java:47`）。

---

## 13. Agent 服務（http://localhost:8100/api/agent，22 端點）

> Agent 有獨立 OpenAPI 文檔：`http://localhost:8100/docs`。注意：agent 響應**不使用**後端的 ApiResponse 信封，為 FastAPI 原生 JSON。

### 13.1 生命週期

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | /start | 啟動優化循環（可帶 initial criteria/config）；已運行則冪等返回 |
| POST | /stop | 停止（cancel asyncio task） |
| GET | /status | 當前狀態：迭代數、best_score、當前階段、階段結果流 |

### 13.2 歷史與配置

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | /history | 迭代歷史（內存最多 100 輪） |
| GET | /history/{iteration} | 單輪詳情 |
| GET/POST | /criteria | 讀/寫當前選股條件 |
| POST | /config | 更新回測配置（校驗日期區間） |
| GET | /data-range | 數據庫最早/最新交易日（供配置回測區間） |

### 13.3 供應商管理

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | /providers | 7 供應商可用性+定價+階段映射 |
| POST | /providers/stage | `{stage, provider}` 設置某階段供應商 |
| POST | /providers/stage/reset | 重置為自動路由 |
| POST | /model/check | 手動觸發全供應商探活 |

### 13.4 監控

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | /health | 後端可達性+模型+RAG+限流+配置概覽 |
| GET | /metrics | **Prometheus 文本格式**（13 個指標） |
| GET | /monitor | 節點事件+告警+統計 |
| GET | /monitor/events | 全部節點事件（時間軸） |
| GET | /monitor/timeline | 按迭代分組（Gantt 用） |
| GET | /monitor/errors | 錯誤/重試經驗（error_store） |
| GET | /monitor/analyze | 監測 AI 分析當前狀態 |
| POST | /monitor/alerts/{alert_id}/resolve | 標記告警已解決 |
| GET | /news/search | 關鍵詞搜財經新聞 |

---

## 14. 調度器配置

### 14.1 ProsperityAlertScheduler（景氣度預警定時調度）

| 配置項 | 默認 | 說明 |
|--------|------|------|
| `ALERT_SCHEDULER_ENABLED` | false | 是否啟用定時預警 |
| `ALERT_SCHEDULER_THRESHOLD` | 15.0 | 預警閾值 |
| `ALERT_SCHEDULER_CRON` | `0 30 15 * * MON-FRI` | Cron（每交易日 15:30 CST） |

- 代碼：`ProsperityAlertScheduler.java`
- 條件裝配：`@ConditionalOnProperty(prefix="app.notification.alert-scheduler", name="enabled", havingValue="true")`
- 啟用後定時調 `industryService.prosperityAlerts(threshold)`，有異常則推送通知

### 14.2 AiCallLogCleanupScheduler（AI 調用日誌清理）

| 配置項 | 默認 | 說明 |
|--------|------|------|
| `AICALLLOG_CLEANUP_ENABLED` | false | 是否啟用定時清理 |
| `AICALLLOG_RETENTION_DAYS` | 90 | 日誌保留天數 |
| `AICALLLOG_CLEANUP_CRON` | `0 0 2 * * *` | Cron（每天凌晨 2:00） |

- 代碼：`AiCallLogCleanupScheduler.java`
- 條件裝配：`@ConditionalOnProperty(prefix="app.aicalllog.cleanup", name="enabled", havingValue="true")`
- 啟用後定時 `DELETE FROM ai_call_log WHERE created_at < NOW() - INTERVAL retention_days DAY`

---

## 15. 契約維護說明

前端 `next/src/lib/api/types.ts`（63 類型）目前為**手寫鏡像**，無生成管線。修改任何 DTO 時必須同步三處：

1. 後端 record（`java/.../dto/`）
2. `next/src/lib/api/types.ts`
3. （若 agent 消費）agent 的解析代碼

規劃改進：以 `openapi-typescript` 從 `/v3/api-docs` 生成類型（見 `DEVELOPMENT.md`）。
