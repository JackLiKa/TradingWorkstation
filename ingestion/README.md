# ingestion/ — Baostock 数据采集

Python 脚本，由后端 `java` 的 `SyncService` 通过 `ProcessBuilder` 编排调用，也可独立运行。
负责从 Baostock 拉取 A 股日线、指数日线、行业分类并幂等写入 MySQL。

## 依赖

```bash
pip install baostock pymysql
```

## 用法

### 交互式模式（推荐用户直接使用）

```bash
python ingestion/baostock_ingest.py
```

进入交互式菜单，提供 13 个选项（歷史獲取 / 增量更新 / 指數 / 行業 / 指定日期範圍等）。

### 命令行模式（後端 API 调用）

```bash
# 增量更新全部三種復權 + 指數 + 行業（最常用，只拉缺失數據）
python ingestion/baostock_ingest.py --mode incremental --adjustflags 1,2,3 --index --industry

# 只同步指數 + 行業（不拉股票）
python ingestion/baostock_ingest.py --mode incremental --adjustflags " " --index --industry

# 強制刷新行業數據（忽略 7 天新鮮度檢查）
python ingestion/baostock_ingest.py --mode incremental --adjustflags " " --industry --force-industry

# 指定日期範圍全量拉取
python ingestion/baostock_ingest.py --mode range --start 2026-08-17 --end 2026-08-17 --adjustflags 1,2,3 --index

# 只更新特定股票
python ingestion/baostock_ingest.py --mode incremental --codes sh.600000,sz.000001 --adjustflag 3
```

## 防重複獲取機制

三層防護確保不會重複拉取或存儲數據：

### 1. 增量拉取（網絡層）

| 數據類型 | 防重複策略 |
|----------|-----------|
| `stock_daily` | 每隻股票 × 復權類型獨立查 `MAX(date)`，只拉 `MAX(date)+1` 之後的數據 |
| `index_daily` | 每個指數獨立查 `MAX(date)`，只拉缺失部分 |
| `stock_industry` | 查 `MAX(update_date)`，若距今 ≤7 天則跳過（baostock 每週一更新）；`--force-industry` 可強制刷新 |

### 2. Upsert 寫入（存儲層）

所有表使用 `ON DUPLICATE KEY UPDATE`，重複運行安全：

| 表 | 唯一鍵 |
|----|--------|
| `stock_daily` | `(code, date, adjustflag)` |
| `index_daily` | `(code, date, frequency)` |
| `stock_industry` | `(code, update_date)` |

### 3. 跳過已完成項（進度層）

- 股票：`stock_start > end` 時跳過該股票（已是最新）
- 指數：`idx_start > end` 時跳過該指數（已是最新）
- 行業：`update_date` 距今 ≤7 天時跳過全量拉取

## 环境变量

从仓库根 `.env` 读取 `DB_*` 与 `SYNC_*`。

## 与后端的协作

后端 `SyncService` 调用本脚本，解析 stdout 进度行（`[info] 已写入 N 条`、`[done] 共写入 N 条`、`[skip] ...`），
维护任务状态与进度，捕获 stderr 错误。详见 `docs/architecture.md`。
