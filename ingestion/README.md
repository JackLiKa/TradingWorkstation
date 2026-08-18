# ingestion/ — Baostock 数据采集

Python 脚本，由后端 `java` 的 `SyncService` 通过 `ProcessBuilder` 编排调用，也可独立运行。
负责从 Baostock 拉取 A 股日线并幂等写入 MySQL `stock_daily`。

## 依赖

```bash
pip install baostock pymysql
```

## 用法

```bash
# 全市场不复权，2021-01-01 至今
python ingestion/baostock_ingest.py --adjustflag 3 --start 2021-01-01

# 指定股票，后复权
python ingestion/baostock_ingest.py --codes sh.600000,sz.000001 --adjustflag 1
```

## 环境变量

从仓库根 `.env` 读取 `DB_*` 与 `SYNC_*`。

## 与后端的协作

后端 `SyncService` 调用本脚本，解析 stdout 进度行（`[info] 已写入 N 条`、`[done] 共写入 N 条`），
维护任务状态与进度，捕获 stderr 错误。详见 `docs/architecture.md`。
