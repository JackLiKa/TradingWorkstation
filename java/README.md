# Java 後端（Trading Workstation Backend）

> Java 21 + Spring Boot 3.3.4 量化交易後端，提供 REST API 供前端與 Agent 服務調用。
> 端口 8090，**context-path 默認 `/TradingWorkstation`**（所有 URL 帶前綴）。
> 深入文檔：架構 [`docs/architecture.md`](../docs/architecture.md)、模塊 [`docs/MODULE_GUIDE.md`](../docs/MODULE_GUIDE.md)、API [`docs/api.md`](../docs/api.md)、回測 [`docs/BACKTEST_ENGINE.md`](../docs/BACKTEST_ENGINE.md)、開發規範 [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md)。

## 技術棧

- Java 21 + Spring Boot 3.3.4（Web / Data JPA / Validation / Cache / Actuator / Mail）
- Hibernate 6.5 + HikariCP（max 20）；`ddl-auto: none` — **JPA 不管理表結構**，schema 真源見 [`docs/database.md`](../docs/database.md)
- Caffeine 內存緩存（10 個緩存，按域拆名，各域獨立 TTL）
- springdoc-openapi（Swagger：`/TradingWorkstation/swagger-ui.html`）
- Lombok、MySQL 8.0+

## 模塊結構（12 個業務模塊）

| 模塊 | 端點前綴 | 職責 |
|------|----------|------|
| `stock` | `/api/stock`（26 端點） | 行情查詢、指數行情、行業日聚合、市場廣度 |
| `industry` | `/api/stock`（行業端點） | 行業景氣度（4 維度評分）、輪動信號、異常預警 |
| `forecast` | `/api/stock`（預測端點） | 輪動預測、Markov 狀態轉移、多模型預測（ARIMA/Holt-Winters/線性回歸）、AutoML、季節性、回測驗證 |
| `indicator` | `/api/indicator`（1 端點） | 指標引擎（註冊表模式），純計算無持久化，被 dashboard/screener/backtest/chart 復用 |
| `dashboard` | `/api/dashboard`（2 端點） | 儀表盤聚合（複用 stock/chart） |
| `chart` | `/api/chart`（2 端點） | K 線分批加載（120 條/批 + 內嵌指標） |
| `screener` | `/api/screener`（1 端點） | 選股器（49 字段條件、parallelStream 過濾） |
| `backtest` | `/api/backtest`（6 端點） | 回測引擎 + 策略庫（backtest_strategy 表，JSON 三列存儲） |
| `sync` | `/api/sync`（3 端點） | ProcessBuilder 編排 ingestion Python 腳本（進度解析 stdout） |
| `system` | `/api/system`（4 端點） | 健康檢查（校驗表/列/索引）、DB 配置、通知（SMTP+Webhook） |
| `preference` | `/api/preference`（2 端點） | 用戶偏好（DB 主存 + 文件降級） |
| `aicalllog` | `/api/aicalllog`（5 端點） | AI 調用日誌（ai_call_log 表，agent 回寫，供可視化） |

## 目錄結構

```text
src/main/java/com/quantization/
├── QuantizationApplication.java       # 入口
├── common/                            # ApiResponse 統一信封、ErrorCode、BusinessException、全局異常、util
├── config/                            # CacheConfig(Caffeine)、AsyncConfig(線程池)、WebConfig(CORS)、OpenApi、AppProperties
│   └── properties/                    # @ConfigurationProperties 綁定類
└── module/
    ├── stock/                         # 行情查詢（StockService 505 行）
    ├── industry/                      # 行業景氣度+預警（IndustryService 513 行）
    ├── forecast/                      # 預測+Markov+AutoML（ForecastService 1,698 行）
    ├── indicator/                     # 指標引擎（註冊表模式）
    │   ├── IndicatorEngine.java       # 註冊表持有 Map<String,IndicatorCalculator>
    │   ├── IndicatorCalculator.java   # 計算器接口（新增指標實現此接口 + @Component）
    │   └── calculator/                # 7 個計算器：MA/BOLL/KDJ/MACD/RSI/Return/VolumeRatio
    ├── dashboard/                     # 儀表盤聚合
    ├── chart/                         # K 線分批加載
    ├── screener/                      # 選股器（ScreenerCore 純函數 + ScreenerService）
    ├── backtest/                      # 回測引擎（BacktestService 22,561 行）
    ├── sync/                          # SyncService（ProcessBuilder + stdout 正則解析進度）
    ├── system/                        # 健康檢查 + NotificationService + ProsperityAlertScheduler
    ├── preference/                    # PreferenceService（DB + 文件降級）
    └── aicalllog/                     # AI 調用日誌 + 清理調度器
```

## 構建

```bash
# 一鍵啟動（推薦，自動加載 .env + JDK21 + 端口檢測）
.\start.ps1

# 手動
mvn -DskipTests compile       # 快速驗證編譯
mvn -DskipTests package       # 打 jar（運行建議 -Xmx4g，回測全市場載內存）
mvn spring-boot:run           # 啟動（需先注入 .env，見 docs/DEPLOYMENT.md §3.2）
mvn test                      # 運行測試（80 個）
```

> **⚠️ `mvn spring-boot:run` 不會自動加載 `.env`**，需先手動注入環境變量。Windows 用 `start.ps1` 腳本自動處理。

驗證：`curl http://localhost:8090/TradingWorkstation/actuator/health` → `{"status":"UP"}`

## 配置

關鍵配置項在 `src/main/resources/application.yml`，從根目錄 `.env` 讀取（`${ENV_VAR:default}` 語法）：

| 配置組 | 關鍵項 | 默認 | 說明 |
|--------|--------|------|------|
| 數據庫 | `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` | localhost/3306/a_stock_baostock/root/— | **DB_PASSWORD 必填** |
| 服務 | `SERVER_PORT`/`SERVER_CONTEXT_PATH` | 8090/`/TradingWorkstation` | context-path 默認帶前綴 |
| 查詢默認 | `DEFAULT_ADJUSTFLAG`/`DEFAULT_LIMIT`/`LOOKBACK_DAYS` | 3/200/180 | 復權默認不復權 |
| 緩存 | `CACHE_*_TTL_SECONDS` | 30-120s | 按域獨立 TTL（見下方緩存設計） |
| 同步 | `SYNC_PYTHON_EXECUTABLE`/`SYNC_INGESTION_SCRIPT`/`SYNC_BATCH_SIZE` | python/ingestion/.../1000 | ProcessBuilder 編排 ingestion |
| 通知 | `NOTIFICATION_ENABLED`/`MAIL_*`/`WEBHOOK_*` | 全 false/空 | 景氣度預警推送 |
| 預警調度 | `ALERT_SCHEDULER_ENABLED`/`ALERT_SCHEDULER_CRON` | false/`0 30 15 * * MON-FRI` | 定時檢查景氣度異常 |

完整環境變量清單見 [`.env.example`](../.env.example) 與 [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md)。

## API

完整 REST API 參考（後端 51 端點 + Agent 22 端點）見 [`docs/api.md`](../docs/api.md)。

Swagger UI：`http://localhost:8090/TradingWorkstation/swagger-ui.html`

統一響應信封：

```json
{ "success": true, "code": "OK", "message": "...", "data": { } }
```

## 測試

**80 個測試**（`src/test/java/com/quantization/test/`），覆蓋：

| 測試文件 | 測試數 | 覆蓋 |
|----------|--------|------|
| `BacktestServiceTest` | — | 回測引擎（滑點、漲跌停、夏普） |
| `IndicatorEngineTest` / `IndicatorMathTest` | — | 指標計算正確性 |
| `ScreenerCoreTest` / `ScreenerFiltersTest` | 13 | 選股條件過濾 |
| `StockServiceAlgorithmTest` | 4 | 行情算法 |
| `PreferenceServiceTest` / `PreferenceRepositoryTest` | — | 偏好存儲（DB + 文件降級） |
| `AiCallLogCleanupSchedulerTest` | — | AI 日誌清理調度 |

```bash
mvn test    # Tests run: 80, Failures: 0, Errors: 0, Skipped: 3
```

## 關鍵設計

### 1. IndicatorEngine 註冊表模式

`IndicatorEngine` 持有 `Map<String, IndicatorCalculator>`，所有計算器由 Spring 自動注入並按 `name()` 註冊。**新增指標只需實現 `IndicatorCalculator` 接口 + `@Component`，無需修改 `IndicatorEngine`**。

```java
// 新增指標示例
@Component
public class MyIndicator implements IndicatorCalculator {
    @Override
    public String name() { return "MY"; }
    @Override
    public void calculate(IndicatorSnapshotBuilder builder, List<StockDaily> history, int index) {
        // 計算邏輯，寫入 builder
    }
}
```

當前已註冊 7 個計算器：MA / BOLL / KDJ / MACD / RSI / Return / VolumeRatio（`module/indicator/calculator/`）。

### 2. ForecastService 三模型集成

`ForecastService`（1,698 行）集成三種預測模型，固定權重加權：

| 模型 | 權重 | 特點 |
|------|------|------|
| ARIMA | 0.35 | AR(2) + 一階差分，捕捉自相關性 |
| Holt-Winters | 0.35 | 三重指數平滑（季節週期=5 交易日），捕捉趨勢+季節性 |
| 線性回歸 | 0.30 | OLS 趨勢預測 |

回測端點會計算最優權重供參考。另含 Markov 狀態轉移（5×5 等級轉移矩陣）、AutoML 調參（15 組合搜尋）、季節性分析。

### 3. BacktestService 滑點+漲跌停+落庫

`BacktestService`（22,561 行）在等權調倉邏輯基礎上增強：

- **滑點**：買賣成交價計入 `slippageBps`（默認 0，可配置）
- **漲跌停約束**：調倉選股跳過當日漲停（pctChg ≥ 9.9）/跌停（pctChg ≤ -9.9）；止損賣出遇跌停延後到下一交易日
- **夏普減無風險利率**：`riskFreeRate` 默認 0.02
- **結果自動落庫**：`runBacktest` 結果寫入 `backtest_strategy` 表（source=auto，best-effort，失敗不影響返回）

### 4. PreferenceService DB+文件降級

`PreferenceService` 主存儲為 MySQL（`user_preference` 表），DB 異常時自動降級到 JSON 文件（路徑由 `PREFERENCE_PATH` 配置）。文件寫入採用臨時文件 + 原子移動（`ATOMIC_MOVE`），synchronized 防併發衝突。

### 5. 緩存 4 域拆名

`CacheConfig` 按業務域拆分 10 個獨立 TTL 的 Caffeine 緩存（max 500 條），避免跨域相互擠占：

| 緩存名 | TTL | 用途 |
|--------|-----|------|
| `dashboardSummary` | 60s | 儀表盤匯總 |
| `dashboardMetrics` / `indexMetadata` / `marketBreadth` / `rotationSignal` / `sectorPerformance` | 30s | 儀表盤指標/指數元數據/市場廣度/輪動/板塊 |
| `stockDaily` | 30s | 行情查詢 |
| `industryDaily` | 60s | 行業聚合/景氣度 |
| `forecast` | 120s | 預測/Markov |
| `rotation` | 120s | 輪動預測 |

新增 `@Cacheable` 時緩存名用 `CacheConfig` 常量並在 CacheManager 註冊。

### 6. 線程池分離

`AsyncConfig` 按用途分離線程池，避免相互阻塞：

| 線程池 | 線程數 | 用途 |
|--------|--------|------|
| `asyncExecutor` | 8 | Dashboard 並行加載等場景 |
| `notificationExecutor` | 4 | 通知推送（郵件/Webhook） |

均為 daemon 線程，固定線程池（避免無限制創建）。

## 開發須知

- DTO 一律 record；可空入參用包裝類型，Service 層填默認值（如 adjustflag null→3）
- 表結構變更必須寫顯式 SQL（`ddl-auto=none`），並同步 Entity/ingestion 建表/`docs/database.md`
- 改後端 DTO 必須同步 `next/src/lib/api/types.ts`（手工鏡像，無生成管線）
- 已知 bug 與債務清單：[`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md) §7

## 已知修復記錄

- `adjustflag null` NPE → Service 層默認 3（`BacktestService.java:76`）
- Maven 本地倉庫非 ASCII 路徑導致 `NoClassDefFoundError` → 倉庫路徑改純 ASCII（`docs/DEPLOYMENT.md` §6.2）
