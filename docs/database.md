# 数据库

MySQL 8.0+，存儲 A 股日線數據（Baostock）、指數行情、行業分類。

## 连接

通过 `.env` 配置：

```
DB_HOST=localhost
DB_PORT=3306
DB_NAME=a_stock_baostock
DB_USER=root
DB_PASSWORD=...
DB_CHARSET=utf8mb4
```

后端 `application.yml` 用 `${DB_HOST:localhost}` 等占位符读取。

## 表结构 `stock_daily`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT AI | 主键 |
| code | VARCHAR(20) | 证券代码 `sh.601713` |
| date | DATE | 交易日期 |
| open / high / low / close / preclose | DECIMAL(20,4) | 价格 |
| volume | BIGINT | 成交量(股) |
| amount | DECIMAL(30,2) | 成交额(元) |
| adjustflag | TINYINT | 1后复权 2前复权 3不复权 |
| turn | DECIMAL(10,4) | 换手率% |
| tradestatus | TINYINT | 1正常 0停牌 |
| pctChg | DECIMAL(10,4) | 涨跌幅% |
| isST | TINYINT | 1是 0否 |
| created_at / updated_at | TIMESTAMP | 自动维护 |

## 索引

- 主键 `id`
- 唯一索引 `uk_code_date_adjust (code, date, adjustflag)` —— 必须含 adjustflag，避免不同复权互相覆盖
- 普通索引 `idx_date`、`idx_code`、`idx_adjustflag`

## 建表 DDL

```sql
CREATE TABLE IF NOT EXISTS stock_daily (
  id BIGINT NOT NULL AUTO_INCREMENT,
  code VARCHAR(20) NOT NULL,
  date DATE NOT NULL,
  open DECIMAL(20,4) NULL,
  high DECIMAL(20,4) NULL,
  low DECIMAL(20,4) NULL,
  close DECIMAL(20,4) NULL,
  preclose DECIMAL(20,4) NULL,
  volume BIGINT NULL,
  amount DECIMAL(30,2) NULL,
  adjustflag TINYINT NULL DEFAULT 3,
  turn DECIMAL(10,4) NULL,
  tradestatus TINYINT NULL DEFAULT 1,
  pctChg DECIMAL(10,4) NULL,
  isST TINYINT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_code_date_adjust (code, date, adjustflag),
  KEY idx_date (date),
  KEY idx_code (code),
  KEY idx_adjustflag (adjustflag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 写入策略

- 同步脚本使用 `INSERT ... ON DUPLICATE KEY UPDATE` 幂等写入。
- 批量插入每 `SYNC_BATCH_SIZE`（默认 1000）条提交一次。

## 表结构 `stock_industry`

股票行業分類表（baostock `query_stock_industry()`，每週一更新）。

```sql
CREATE TABLE IF NOT EXISTS stock_industry (
  id bigint NOT NULL AUTO_INCREMENT,
  code varchar(20) NOT NULL COMMENT '證券代碼（sh.600000 或 sz.000001）',
  update_date date NOT NULL COMMENT '行業數據更新日期',
  code_name varchar(50) DEFAULT NULL COMMENT '證券名稱',
  industry varchar(100) DEFAULT NULL COMMENT '所屬行業',
  industry_classification varchar(50) DEFAULT NULL COMMENT '行業分類標準',
  created_at timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_code_date (code, update_date),
  KEY idx_industry (industry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

- 唯一键 `(code, update_date)`：同一股票同一更新日期只保留一条。
- 行業數據與 adjustflag 無關，獨立存儲，查詢時 JOIN。
- 同步命令：`python ingestion/baostock_ingest.py --industry` 或 `--mode incremental --adjustflags 1,2,3 --index --industry`。

## 表結構 `index_daily`

指數日線數據表（baostock `query_history_k_data_plus()`，用於指數行情）。

```sql
CREATE TABLE IF NOT EXISTS index_daily (
  id bigint NOT NULL AUTO_INCREMENT,
  code varchar(20) NOT NULL COMMENT '指數代碼（sh.000001 上證指數等）',
  date date NOT NULL,
  open DECIMAL(20,4) NULL,
  high DECIMAL(20,4) NULL,
  low DECIMAL(20,4) NULL,
  close DECIMAL(20,4) NULL,
  preclose DECIMAL(20,4) NULL,
  volume BIGINT NULL,
  amount DECIMAL(30,2) NULL,
  frequency varchar(10) DEFAULT 'D' COMMENT '頻率：D 日線 W 週線 M 月線',
  created_at timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_code_date_freq (code, date, frequency),
  KEY idx_date (date),
  KEY idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## 表結構 `index_metadata`

指數元數據表（來自 `ingestion/index_list.json`）：代碼、名稱、分類、數據來源。
支持 10 大類別 ~80 個指數：綜合（composite）、規模（scale）、一級行業（industry_l1）、二級行業（industry_l2）、策略（strategy）、成長（growth）、價值（value）、主題（theme）、基金（fund）、債券（bond）。

```sql
CREATE TABLE IF NOT EXISTS index_metadata (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code VARCHAR(16) NOT NULL COMMENT '指數代碼（sh.000001 / sz.399001）',
  name VARCHAR(64) NOT NULL COMMENT '指數名稱',
  category VARCHAR(32) NOT NULL COMMENT '分類中文名',
  category_code VARCHAR(32) NOT NULL COMMENT '分類英文代碼',
  source VARCHAR(32) NOT NULL DEFAULT 'baostock' COMMENT '數據來源',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_index_metadata_code (code),
  KEY idx_index_metadata_category (category_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='指數元數據';
```

## 表結構 `backtest_strategy`

AI 優化策略存儲表（Agent 服務每輪優化後持久化）。

```sql
CREATE TABLE IF NOT EXISTS backtest_strategy (
  id bigint NOT NULL AUTO_INCREMENT,
  name varchar(100) NOT NULL COMMENT '策略名稱',
  criteria json NOT NULL COMMENT '選股條件 JSON',
  config json NULL COMMENT '回測配置 JSON',
  composite_score DECIMAL(10,2) DEFAULT 0 COMMENT '綜合評分',
  total_return DECIMAL(10,2) NULL COMMENT '總收益率%',
  max_drawdown DECIMAL(10,2) NULL COMMENT '最大回撤%',
  sharpe DECIMAL(10,4) NULL COMMENT '夏普比率',
  status varchar(20) DEFAULT 'active' COMMENT 'active/archived',
  created_at timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_score (composite_score),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

- Agent 每輪優化完成後，策略和評分寫入此表。
- 前端可通過 `/TradingWorkstation/api/backtest/strategies` 查詢歷史策略。

