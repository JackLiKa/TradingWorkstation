# 回測引擎專題（Backtest Engine）

> 對應代碼：`java/src/main/java/com/quantization/module/backtest/`
> 核心入口：`BacktestService.runBacktest()`（`BacktestService.java:79-286`）
> 定位：**研究級信號驗證工具**，非交易級撮合模擬。使用前必讀 §6 方法論限制。

---

## 1. 回測流程總覽

回測引擎模擬「調倉日選股 → 等權買入 → 持有 → 止損/止盈 → 賣出 → 統計」的完整閉環，以收盤價撮合、逐日估值淨值曲線。

```mermaid
flowchart TD
    A["BacktestRequestDto<br/>criteria(選股49字段) + config(回測配置)"] --> B["參數歸一化<br/>adjustflag null→3<br/>slippageRate / riskFreeRate"]
    B --> C["拉數據<br/>交易日列 + start-320天起全市場行情<br/>+ 基準 sh.000001 + 行業Map"]
    C --> D["逐交易日推進"]
    D --> E{"止損/止盈觸發?"}
    E -->|是 且 非跌停| F["賣出<br/>price×(1-slippage)×(1-commission)"]
    E -->|是 但 跌停| G["延後到下一交易日"]
    D --> H{"調倉日?"}
    H -->|是| I["到期持倉平倉<br/>持有天數≥holdingPeriod"]
    I --> J["screenerCore.screenAt()<br/>當日快照選股 → 漲跌停過濾"]
    J --> K["等權買入<br/>price×(1+slippage)×(1+commission)"]
    F & K --> L["逐日記三條淨值曲線<br/>strategy / benchmark / excess"]
    L --> M["computeStatistics()<br/>總收益/年化/回撤/夏普(減rf)"]
    M --> N["saveAndReturn()<br/>自動落庫 source=auto"]
    N --> O["BacktestResultDto"]
```

### 1.1 各階段對應代碼行號

| 階段 | 代碼位置 | 說明 |
|------|----------|------|
| 參數歸一化 | `BacktestService.java:80-97` | adjustflag null→3、slippageRate、riskFreeRate 提取 |
| 數據準備 | `:99-163` | 交易日曆、調倉日列表、全市場行情載入、基準指數 |
| 止損/止盈 | `:178-205` | 跌停延後賣出、滑點下浮 |
| 調倉平倉 | `:208-227` | 持有期到期判斷、滑點下浮 |
| 選股+買入 | `:229-258` | 漲跌停過濾、滑點上浮、等權分配 |
| 估值記錄 | `:261-279` | 收盤價估值（不含滑點）、基準累計 |
| 統計計算 | `:281-282` | 調用 `computeStatistics()` |
| 自動落庫 | `:285` | 調用 `saveAndReturn()` |

---

## 2. 配置參數（BacktestConfigDto）

完整字段定義見 `dto/BacktestConfigDto.java:20-32`，record 含 11 個字段：

| 字段 | 類型 | 默認 | 說明 |
|------|------|------|------|
| `startDate` | `LocalDate` | — | 回測起始日期 |
| `endDate` | `LocalDate` | — | 回測結束日期 |
| `rebalanceInterval` | `int` | — | 調倉間隔（交易日數） |
| `holdingPeriod` | `int` | — | 持有期（交易日），到期強制平倉 |
| `maxPositions` | `int` | — | 最大持倉數 |
| `initialCapital` | `double` | — | 初始資金 |
| `commissionBps` | `double` | — | 手續費基點（1bp=0.01%，買賣雙邊收取） |
| `stopLossPct` | `Double` | `null` | 止損百分比，null=不啟用 |
| `takeProfitPct` | `Double` | `null` | 止盈百分比，null=不啟用 |
| **`riskFreeRate`** | `Double` | **0.02** | 無風險年化利率，用於夏普比率計算（Phase 4 新增） |
| **`slippageBps`** | `Integer` | **0** | 滑點基點，買入上浮/賣出下浮（Phase 4 新增） |

### 2.1 默認值與空安全

`BacktestConfigDto` 的緊湊構造器（`:38-41`）對新增字段做空安全處理：

```java
public BacktestConfigDto {
    if (riskFreeRate == null) riskFreeRate = DEFAULT_RISK_FREE_RATE;  // 0.02
    if (slippageBps == null) slippageBps = DEFAULT_SLIPPAGE_BPS;     // 0
}
```

並提供 `effectiveRiskFreeRate()`（`:44-46`）和 `effectiveSlippageBps()`（`:49-51`）方法，保證永遠返回非 null 值。`BacktestService` 在 `:89-90` 使用這兩個方法提取有效值。

### 2.2 請求示例

```json
{
  "criteria": { "...": "ScreenerCriteriaDto，49 字段，adjustflag 可空默認 3" },
  "config": {
    "startDate": "2025-01-01",
    "endDate": "2025-06-30",
    "rebalanceInterval": 5,
    "holdingPeriod": 10,
    "maxPositions": 10,
    "initialCapital": 1000000,
    "commissionBps": 3,
    "stopLossPct": null,
    "takeProfitPct": null,
    "riskFreeRate": 0.02,
    "slippageBps": 10
  }
}
```

---

## 3. 滑點模型（Phase 4 新增）

滑點模擬買賣時的價格偏移，`slippageRate = effectiveSlippageBps() / 10000.0`（`BacktestService.java:89`）。

| 方向 | 成交價公式 | 代碼位置 | 說明 |
|------|-----------|----------|------|
| **買入** | `price × (1 + slippageRate)` | `:249` | 上浮滑點，模擬買入衝擊成本 |
| **賣出** | `price × (1 - slippageRate)` | `:201, :220` | 下浮滑點，模擬賣出衝擊成本 |
| 估值 | `price`（不含滑點） | `:265` | 逐日以收盤價估值持倉市值 |

**示例**：`slippageBps=10`（1bp=0.01%），買入成交價 = `price × 1.001`，賣出成交價 = `price × 0.999`。

> ⚠️ **限制**：固定 bps 滑點模型，非市場衝擊模型（不隨成交量/流動性變化）。真實大單交易的滑點會顯著高於固定 bps 值，見 §6。

---

## 4. 漲跌停約束（Phase 4 新增）

漲跌停閾值 `LIMIT_THRESHOLD = 9.9`（`BacktestService.java:60`），即 `|pctChg| ≥ 9.9` 視為漲跌停。

| 場景 | 規則 | 代碼位置 | 理由 |
|------|------|----------|------|
| **買入選股** | `|pctChg| ≥ 9.9` 跳過 | `:232-240` | 漲停買不進、跌停不選 |
| **止損賣出** | `pctChg ≤ -9.9` 延後到下一交易日 | `:186-190` | 跌停板無法成交，延後賣出 |

選股時多取候選（`candidateLimit = maxPositions × 3`，`:230`），過濾漲跌停後仍有足夠標的填充倉位。

---

## 5. 夏普比率（Phase 4 改進）

夏普比率現在扣除無風險利率（`computeStatistics()`，`:345-385`）：

```
sharpe = (mean(日收益) - rf/252) / std(日收益) × √252
```

| 步驟 | 代碼行 | 說明 |
|------|--------|------|
| 日收益序列 | `:369-374` | `cur/prev - 1`，小數形式 |
| 日均收益 | `:377` | `dailyReturns` 算術平均 |
| 日標準差 | `:378` | 总體標準差（除以 N） |
| 日無風險利率 | `:379` | `riskFreeRate / 252.0` |
| 年化夏普 | `:380` | `(mean - dailyRiskFree) / std × √252` |

- `riskFreeRate` 默認 `0.02`（`DEFAULT_RISK_FREE_RATE`，`:34`）
- `rf=0` 時與原公式一致；`rf>0` 時夏普更低（更保守）
- `std=0` 時夏普返回 0（避免除零）

### 5.1 其他統計指標

| 指標 | 公式 | 代碼行 |
|------|------|--------|
| `totalReturn` | `(final/initial - 1) × 100` | `:353` |
| `annualReturn` | `(pow(final/initial, 1/years) - 1) × 100` | `:358` |
| `benchmarkReturn` | 基準同式（上證綜指） | `:354` |
| `excessReturn` | `totalReturn - benchmarkReturn` | `:355` |
| `maxDrawdown` | `max((peak - v)/peak) × 100` | `:360-366` |
| `rebalanceCount` | 調倉次數 | `:382` |
| `totalTrades` | 買賣總筆數 | `:383` |

---

## 6. 方法論限制（使用者必讀）

| # | 限制 | 影響 | 狀態 |
|---|------|------|------|
| 1 | **止損/止盈假設觸發價成交** | 漲跌停/流動性不足時可能無法成交，止損保護效果被高估——尤其連續跌停場景 | 已加跌停延後賣出（§4），但極端行情仍樂觀 |
| 2 | **ST/行業 survivorship bias** | `stock_industry` 存當前分類（非時點值），`excludeSt=true` 過濾的是「現在的 ST 股」而非「當時的 ST 股」；已退市股不出現在回測中 | 數據源限制，難修 |
| 3 | **固定 bps 滑點模型** | 非市場衝擊模型，不隨成交量/流動性變化；大單真實滑點顯著高於固定值 | 已加 `slippageBps` 配置，但模型簡化 |
| 4 | **無最小手數** | 股數可為任意小數，小資金回測偏樂觀 | 可接受的研究簡化 |
| 5 | **等權配置** | 無按流動性/波動率加權 | 設計選擇 |
| 6 | **基準固定上證綜指** | 中小盤策略應對比中證500/1000 | 建議配置化 |
| 7 | **無分紅/資金費處理** | 長周期回測分紅缺失使收益低估 | 已知限制 |

> **結論**：回測結果適合**策略相對比較與參數方向判斷**，絕對收益數字不可直接外推實盤。

---

## 7. 結果落庫（Phase 4 新增）

`runBacktest()` 結束時自動調用 `saveAndReturn()`（`:412-432`），將結果寫入 `backtest_strategy` 表：

| 步驟 | 代碼行 | 說明 |
|------|--------|------|
| 序列化 | `:414-416` | criteria/config/result → JSON 三列 |
| 命名 | `:419-420` | `回測-yyyyMMdd-HHmmss` |
| source | `:424` | 固定 `auto`（區分 `manual` 手動保存） |
| 保存 | `:427` | `strategyRepository.save(entity)` |
| 容錯 | `:428-430` | 落庫失敗僅記 WARN 日誌，**不影響結果返回** |

### 7.1 查詢最近記錄

`listRecentRuns(int limit)`（`:294-299`）按創建時間倒序返回最近 N 次記錄，對應 `GET /api/backtest/recent`。

> **注意**：`/run-and-save` 端點（`BacktestController.java:62-66`）自 Phase 4 後與 `/run` 行為等價（`runBacktest` 已內置自動落庫），保留路徑僅為 API 兼容性。

---

## 8. API 端點

| 方法 | 路徑 | 說明 | 代碼位置 |
|------|------|------|----------|
| `POST` | `/api/backtest/run` | 運行回測（自動落庫） | `BacktestController.java:46-49` |
| `POST` | `/api/backtest/run-and-save` | 等價於 `/run`（兼容保留） | `:62-66` |
| `GET` | `/api/backtest/recent?limit=20` | 最近 N 次回測記錄 | `:87-91` |
| `POST` | `/api/backtest/strategies` | 手動保存策略（source=manual） | `:75-78` |
| `GET` | `/api/backtest/strategies?source=` | 策略列表 | `:99-103` |
| `GET` | `/api/backtest/strategies/{id}` | 策略詳情 | `:112-115` |
| `DELETE` | `/api/backtest/strategies/{id}` | 刪除策略 | `:124-127` |

> ⚠️ **context-path**：實際請求需帶 `/TradingWorkstation` 前綴，如 `POST /TradingWorkstation/api/backtest/run`。

### 8.1 請求/響應格式

**請求**：`BacktestRequestDto`（`criteria: ScreenerCriteriaDto` + `config: BacktestConfigDto`）

**響應**：`ApiResponse<BacktestResultDto>`，統一信封 `{code, message, data}`

`BacktestResultDto`（`dto/BacktestResultDto.java:17-25`）含：
- `config`：回測配置回顯
- `strategyCurve` / `benchmarkCurve` / `excessCurve`：三條 `EquityPoint[]{date, value}` 淨值曲線
- `rebalances`：`RebalanceEvent[]{date, bought[], sold[], held[]}` 調倉明細
- `statistics`：`BacktestStatistics`（8 個指標，見 §5）
- `logLines`：過程摘要（含滑點/無風險利率信息，`:391-401`）

---

## 9. 測試覆蓋

`BacktestServiceTest`（`src/test/java/com/quantization/test/BacktestServiceTest.java`）共 **7 個測試**，使用 Mockito mock `StockService` 避免數據庫依賴：

| 測試方法 | 行號 | 覆蓋場景 |
|----------|------|----------|
| `runBacktestBuildsMetricsAndCurves` | `:57-97` | 完整回測生成曲線/調倉/統計，驗證 logLines 含「無風險利率」 |
| `stopLossTriggersExit` | `:100-139` | 止損觸發平倉（構造 low=entry×0.92 觸發 5% 止損） |
| `emptyDataReturnsEmptyResult` | `:142-162` | 空數據返回空結果 |
| `runBacktestAutoPersistsResult` | `:165-203` | 自動落庫：驗證 `save()` 調用、resultJson 非空、source=auto |
| `listRecentRunsReturnsLimitedRecords` | `:206-225` | listRecentRuns 返回限制條數、調用 findRecentRuns |
| `slippageAppliedToFillPrice` | `:228-258` | 滑點配置生效：logLines 含「滑點：50 bp」 |
| `sharpeDeductsRiskFreeRate` | `:261-289` | rf=0 vs rf=0.5，高 rf 夏普更低 |

---

## 10. 性能與運維注意

- **內存**：單次回測全市場載入內存（3354 股 × ~540 日 ≈ 180 萬記錄），建議 JVM `-Xmx4g`
- **超時**：回測是同步請求，前端 `proxyTimeout: 180s`、agent 端 600s 超時——調長回測區間時注意兩處
- **確定性**：引擎確定性，同一請求兩次結果應相同（若不同檢查數據是否被同步任務更新）
- **緩存**：後端 Caffeine 緩存 TTL 30s，同步後最多等 30s 或重啟後端

---

## 11. 常見問題

| 問題 | 原因/解法 |
|------|-----------|
| `NullPointerException: adjustflag() is null` | 舊版本 bug，已修（Service 層 `:97` 默認 3）；若復現檢查是否走了舊 jar |
| 回測結果為空曲線 | 回測區間內無交易日數據——先查 `/api/agent/data-range` 或 stock_daily 日期範圍 |
| 回測超時 | 區間過長/選股條件過鬆導致調倉頻繁；縮短區間或加大 `rebalanceInterval` |
| 夏普比舊版偏高 | Phase 4 前未減無風險利率，現已修正（默認 rf=0.02） |
| 滑點未生效 | 檢查 `slippageBps` 是否為 null/0；用 `effectiveSlippageBps()` 確認 |
