# 數據採集（Trading Workstation Ingestion）

> Python Baostock 數據採集工具，由 Java 後端 `SyncService` 通過 `ProcessBuilder` 編排。
> 深入文檔：[`docs/DATA_INGESTION.md`](../docs/DATA_INGESTION.md)、數據庫 Schema [`docs/database.md`](../docs/database.md)、部署 [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md)。

## 技術棧

Python 3.10+ / Baostock 0.8.8+ / PyMySQL 1.1.0+

## 三模塊結構

```text
ingestion/
├── baostock_fetch.py       # API 調用層：Baostock 登入/會話、股票/指數 API、清單加載、原始值解析
├── baostock_write.py       # DB 寫入層：環境加載、MySQL 連接、增量日期查詢、批量 upsert、元數據/行業聚合寫入
├── baostock_ingest.py      # 入口層：CLI、交互式菜單、編排、進度輸出（調用 fetch/write）
├── stock_list.json         # 股票清單（3354 隻 A 股，靜態文件）
├── index_list.json         # 指數清單（10 大類別 ~80 個指數，含代碼/名稱/分類）
└── requirements.txt        # baostock>=0.8.8, pymysql>=1.1.0
```

| 模塊 | 職責 |
|------|------|
| `baostock_fetch.py` | Baostock login/session 管理、`query_history_k_data_plus`/`query_history_k_data_plus`（指數）API 調用、股票/指數清單加載、原始值解析 |
| `baostock_write.py` | 從根目錄 `.env` 加載 `DB_*` 環境變量、建立 PyMySQL 連接、查詢每隻股票已有最新日期（增量模式）、批量 `ON DUPLICATE KEY UPDATE` upsert、`index_metadata`/`stock_industry`/`industry_daily` 聚合寫入 |
| `baostock_ingest.py` | CLI 參數解析、14 選項交互式菜單、編排 fetch→write 流程、進度輸出（stdout 中文短語 / `--progress-json` JSON 事件） |

## 安裝

```bash
pip install -r ingestion/requirements.txt
# 依賴：baostock>=0.8.8, pymysql>=1.1.0
```

## 數據庫配置

從**根目錄 `.env`** 讀取（與 Java 後端共用同一份配置）：

| 環境變量 | 默認 | 說明 |
|----------|------|------|
| `DB_HOST` | localhost | MySQL 主機 |
| `DB_PORT` | 3306 | MySQL 端口 |
| `DB_NAME` | a_stock_baostock | 庫名 |
| `DB_USER` | root | 用戶名 |
| `DB_PASSWORD` | （空） | **必填** |
| `DB_CHARSET` | utf8mb4 | 字符集 |

> **⚠️ 無 `DATABASE_URL`**：當前實現使用獨立的 `DB_*` 變量，不支持單一連接字符串。

## 寫入的數據表

| 表 | 唯一鍵 | 寫入方式 | 說明 |
|----|--------|----------|------|
| `stock_daily` | `(code, date, adjustflag)` | `ON DUPLICATE KEY UPDATE` | 日線行情（3 種復權） |
| `index_daily` | `(code, date, frequency)` | `ON DUPLICATE KEY UPDATE` | 指數日線 |
| `index_metadata` | `code` | upsert | 指數元數據（名稱/分類） |
| `stock_industry` | `code` | upsert | 股票行業分類 |
| `industry_daily` | `(industry, date)` | 聚合 upsert | 行業日聚合（由 `stock_daily` + `stock_industry` 計算） |

所有寫入均為冪等（`ON DUPLICATE KEY UPDATE`），重複運行安全。

## CLI 參數

```bash
python ingestion/baostock_ingest.py [選項]
```

| 參數 | 值 | 說明 |
|------|----|------|
| `--mode` | `incremental` \| `range` | `incremental`：每隻股票只拉缺失日期；`range`：拉指定日期範圍全部數據 |
| `--adjustflag` | `1` \| `2` \| `3` | 單一復權類型（1=後復權，2=前復權，3=不復權） |
| `--adjustflags` | `1,2,3` | 多種復權類型（逗號分隔，空字符串=不拉股票） |
| `--start` | `YYYY-MM-DD` | 日期範圍起始（`range` 模式） |
| `--end` | `YYYY-MM-DD` | 日期範圍結束（`range` 模式） |
| `--codes` | `sh.600000,sz.000001` | 指定股票代碼（逗號分隔） |
| `--batch-size` | `1000` | 批量寫入大小 |
| `--index` | flag | 同步指數數據 |
| `--industry` | flag | 同步行業分類 + `industry_daily` 聚合 |
| `--force-industry` | flag | 強制重建 `stock_industry`（覆蓋現有） |
| `--full-refresh-adjustflag2` | flag | **全量刷新前復權數據**（對策見下方） |
| `--progress-json` | flag | 機器可讀 JSON 進度協議（stdout JSON 事件，stderr 中文日誌） |

### 復權類型

| adjustflag | 含義 |
|------------|------|
| 1 | 後復權 |
| 2 | 前復權 |
| 3 | 不復權（`industry_daily` 聚合用此類） |

## 使用示例

```bash
# 交互式菜單（14 選項，推薦首次使用）
python ingestion/baostock_ingest.py

# 增量更新全部（三種復權 + 指數 + 行業，最常用）
python ingestion/baostock_ingest.py --mode incremental --adjustflags 1,2,3 --index --industry

# 指定日期範圍全量拉取
python ingestion/baostock_ingest.py --mode range --start 2021-01-01 --adjustflag 2

# 只更新特定股票
python ingestion/baostock_ingest.py --mode incremental --codes sh.600000,sz.000001 --adjustflag 3

# 只同步指數
python ingestion/baostock_ingest.py --mode incremental --adjustflags "" --index

# 全量刷新前復權（每季度執行，對策見下方）
python ingestion/baostock_ingest.py --full-refresh-adjustflag2 --adjustflags 2
```

## ⚠️ 前復權數據陳舊化風險

**問題**：Baostock 在派息/拆股後會重算**整個歷史**的前復權序列。增量模式只拉 `MAX(date)` 之後的數據，因此舊的 `adjustflag=2` 數據會變得陳舊。

**影響**：前復權（adjustflag=2）的歷史價格與 Baostock 最新計算不一致，導致回測/指標計算偏差。

**對策**：每季度執行一次全量刷新：

```bash
# 方法 1：一鍵全量刷新前復權（推薦）
python ingestion/baostock_ingest.py --full-refresh-adjustflag2 --adjustflags 2

# 方法 2：顯式日期範圍刷新
python ingestion/baostock_ingest.py --mode range --start 2021-01-01 --adjustflag 2
```

> 不復權數據（adjustflag=3）無此問題，`industry_daily` 聚合使用不復權數據。

## 進度協議

### 默認模式（人類可讀）

stdout 輸出包含中文短語，Java `SyncService` 通過正則匹配解析進度：

- `已寫入 N 條` — 單隻股票寫入完成
- `共寫入 N 條` — 全部寫入完成

> **⚠️ 這些中文短語是與 Java `SyncService` 的契約，不可修改**。`SyncService` 用 `ProcessBuilder` 啟動進程並合併 stderr 到 stdout，通過正則匹配這些短語來報告進度。

### `--progress-json` 模式（機器可讀）

```bash
python ingestion/baostock_ingest.py --mode incremental --adjustflags 3 --progress-json
```

- **stdout**：JSON 事件行（每行一個 JSON 對象）
- **stderr**：人類可讀中文日誌

JSON 事件類型：

| 事件類型 | 字段 | 說明 |
|----------|------|------|
| `progress` | `type`, `code`, `written`, `total` | 單隻股票進度 |
| `done` | `type`, `total_written` | 全部完成 |
| `error` | `type`, `code`, `error` | 單隻股票錯誤 |

## 後端編排

Java 後端 `SyncService`（`module/sync/`）通過 `ProcessBuilder` 編排本腳本：

1. 構建命令：`python ingestion/baostock_ingest.py --mode <mode> --adjustflags <flags> [--index] [--industry] --progress-json`
2. 合併 stderr → stdout
3. 逐行讀取 stdout，正則匹配 `已寫入 N 條` / `共寫入 N 條` 報告進度
4. 等待進程結束，返回退出碼

**API 端點**：

```bash
# 啟動同步
curl -X POST http://localhost:8090/TradingWorkstation/api/sync/run \
  -H "Content-Type: application/json" \
  -d '{"mode":"incremental","adjustflags":"1,2,3","syncIndex":true,"syncIndustry":true}'

# 查詢狀態
curl http://localhost:8090/TradingWorkstation/api/sync/status

# 取消
curl -X POST http://localhost:8090/TradingWorkstation/api/sync/cancel
```

> **⚠️ 協議耦合**：修改 `baostock_ingest.py` 的 stdout 輸出格式（尤其是中文短語）會破壞 Java `SyncService` 的進度解析。如需修改進度協議，必須同步更新 `SyncService` 的正則匹配邏輯。
