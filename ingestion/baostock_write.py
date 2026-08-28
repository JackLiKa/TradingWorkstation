"""資料庫寫入層 — 連接、查詢、批量 upsert、指數元數據與行業日聚合。

從 baostock_ingest.py 拆分而來（P5 三模塊重構），職責：
- 資料庫連接與環境變量載入
- 增量更新所需的最新日期 / 已存在清單查詢
- stock_daily / index_daily / stock_industry 批量 upsert
- index_metadata 同步、industry_daily 聚合寫入

本模塊僅依賴 pymysql 與標準庫，不涉及 Baostock API 調用。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pymysql


# ============================================================================
# 環境與資料庫連接
# ============================================================================

def _load_env(root: Path) -> None:
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _connect() -> pymysql.Connection:
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "a_stock_baostock"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        charset=os.getenv("DB_CHARSET", "utf8mb4"),
        autocommit=False,
    )


# ============================================================================
# 增量更新查詢
# ============================================================================

def _get_stock_last_date(conn, code: str, adjustflag: int):
    """獲取某隻股票在某個復權類型下的最新交易日期。"""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT MAX(date) FROM stock_daily WHERE code = %s AND adjustflag = %s",
            (code, adjustflag),
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else None


def _get_index_last_date(conn, code: str, frequency: str = "d"):
    """獲取某個指數在某個週期下的最新交易日期。"""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT MAX(date) FROM index_daily WHERE code = %s AND frequency = %s",
            (code, frequency),
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else None


def _get_existing_stocks(conn, adjustflag: int) -> list[str]:
    """獲取資料庫中已存在某個復權類型數據的股票列表。"""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT code FROM stock_daily WHERE adjustflag = %s ORDER BY code",
            (adjustflag,),
        )
        return [row[0] for row in cursor.fetchall()]


def _get_existing_indexes(conn, frequency: str = "d") -> list[str]:
    """獲取資料庫中已存在的指數列表。"""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT code FROM index_daily WHERE frequency = %s ORDER BY code",
            (frequency,),
        )
        return [row[0] for row in cursor.fetchall()]


# ============================================================================
# 批量 upsert
# ============================================================================

def _upsert_stock_batch(cursor, rows: list[tuple]) -> None:
    if not rows:
        return
    sql = (
        "INSERT INTO stock_daily "
        "(code,date,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE "
        "open=VALUES(open),high=VALUES(high),low=VALUES(low),close=VALUES(close),"
        "preclose=VALUES(preclose),volume=VALUES(volume),amount=VALUES(amount),"
        "turn=VALUES(turn),tradestatus=VALUES(tradestatus),pctChg=VALUES(pctChg),isST=VALUES(isST)"
    )
    cursor.executemany(sql, rows)


def _upsert_index_batch(cursor, rows: list[tuple]) -> None:
    if not rows:
        return
    sql = (
        "INSERT INTO index_daily "
        "(code,date,open,high,low,close,preclose,volume,amount,pctChg,frequency,source) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'d','baostock') "
        "ON DUPLICATE KEY UPDATE "
        "open=VALUES(open),high=VALUES(high),low=VALUES(low),close=VALUES(close),"
        "preclose=VALUES(preclose),volume=VALUES(volume),amount=VALUES(amount),pctChg=VALUES(pctChg)"
    )
    cursor.executemany(sql, rows)


def _upsert_industry_batch(cursor, rows: list[tuple]) -> None:
    """批量 upsert 行業數據。rows = [(code, update_date, code_name, industry, industry_classification), ...]"""
    if not rows:
        return
    sql = (
        "INSERT INTO stock_industry "
        "(code, update_date, code_name, industry, industry_classification) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "code_name=VALUES(code_name), industry=VALUES(industry), "
        "industry_classification=VALUES(industry_classification), update_date=VALUES(update_date)"
    )
    cursor.executemany(sql, rows)


def _infer_board(code: str, is_st: int) -> str:
    """根據股票代碼前綴和 ST 標誌推斷板塊。

    Args:
        code: 股票代碼（如 sh.688001、sz.300001、sz.000001）
        is_st: 是否為 ST 股（1=ST, 0=非 ST）

    Returns:
        str: 板塊標識（main/star/chinext/st）
    """
    if is_st == 1:
        return "st"
    if code.startswith("sh.688"):
        return "star"  # 科創板
    if code.startswith("sz.300"):
        return "chinext"  # 創業板
    return "main"  # 主板


def _upsert_stock_listing_batch(cursor, rows: list[tuple]) -> None:
    """批量 upsert 股票上市狀態。

    rows = [(code, code_name, board, listing_date, delisting_date), ...]
    用於消除倖存者偏差：回測時按日期過濾在市股票。
    """
    if not rows:
        return
    sql = (
        "INSERT INTO stock_listing "
        "(code, code_name, board, listing_date, delisting_date, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP) "
        "ON DUPLICATE KEY UPDATE "
        "code_name=VALUES(code_name), board=VALUES(board), "
        "listing_date=VALUES(listing_date), delisting_date=VALUES(delisting_date), "
        "updated_at=CURRENT_TIMESTAMP"
    )
    cursor.executemany(sql, rows)


def _get_industry_last_update_date(conn):
    """獲取 stock_industry 表中最新的 update_date。"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT MAX(update_date) FROM stock_industry")
        result = cursor.fetchone()
        return result[0] if result and result[0] else None


# ============================================================================
# 指數元數據與行業日聚合
# ============================================================================

def _sync_index_metadata(conn) -> int:
    """從 index_list.json 同步指數元數據到 index_metadata 表。

    新格式的 index_list.json 包含分類信息，此函數將其寫入數據庫，
    供 Java 後端 /api/stock/index-list 端點查詢。

    Returns:
        int: 寫入/更新的元數據條數
    """
    list_path = Path(__file__).resolve().parent / "index_list.json"
    if not list_path.exists():
        return 0
    data = json.loads(list_path.read_text(encoding="utf-8"))
    if "categories" not in data:
        return 0  # 舊格式無元數據

    rows = []
    for cat in data["categories"]:
        category = cat["category"]
        category_code = cat["category_code"]
        for idx in cat.get("indices", []):
            rows.append((idx["code"], idx["name"], category, category_code, "baostock"))

    if not rows:
        return 0

    with conn.cursor() as cursor:
        sql = (
            "INSERT INTO index_metadata (code, name, category, category_code, source) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE name=VALUES(name), category=VALUES(category), "
            "category_code=VALUES(category_code), source=VALUES(source)"
        )
        cursor.executemany(sql, rows)
        conn.commit()
        print(f"[done] 指數元數據已同步 {len(rows)} 條（10 大類別）")
        return len(rows)


def _sync_industry_daily(conn, start: str, end: str) -> int:
    """按 (date, industry) 聚合 stock_daily + stock_industry，寫入 industry_daily。

    只重算 [start, end] 區間內尚未聚合的日期（基於 stock_daily adjustflag=3 的數據），
    用於支持行業級日度分析：均漲跌、總成交、漲跌家數等。
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS industry_daily (
      id BIGINT NOT NULL AUTO_INCREMENT,
      date DATE NOT NULL COMMENT '交易日',
      industry VARCHAR(100) NOT NULL COMMENT '行業名稱',
      stock_count INT NOT NULL DEFAULT 0 COMMENT '該行業當日股票數量',
      avg_pct_chg DECIMAL(20,6) NULL COMMENT '平均漲跌幅',
      total_amount DECIMAL(30,2) NULL COMMENT '總成交金額',
      total_volume BIGINT NULL COMMENT '總成交量',
      avg_turn DECIMAL(20,6) NULL COMMENT '平均換手率',
      rising_count INT NULL DEFAULT 0 COMMENT '上漲家數',
      falling_count INT NULL DEFAULT 0 COMMENT '下跌家數',
      avg_close DECIMAL(20,4) NULL COMMENT '平均收盤價',
      max_close DECIMAL(20,4) NULL COMMENT '最高收盤價',
      min_close DECIMAL(20,4) NULL COMMENT '最低收盤價',
      created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      UNIQUE KEY uk_date_industry (date, industry),
      KEY idx_date (date),
      KEY idx_industry (industry)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='行業日度聚合數據'
    """

    agg_sql = """
    INSERT INTO industry_daily
    (date, industry, stock_count, avg_pct_chg, total_amount, total_volume, avg_turn,
     rising_count, falling_count, avg_close, max_close, min_close)
    SELECT
      d.date,
      i.industry,
      COUNT(*) AS stock_count,
      AVG(d.pctChg) AS avg_pct_chg,
      SUM(d.amount) AS total_amount,
      SUM(d.volume) AS total_volume,
      AVG(d.turn) AS avg_turn,
      SUM(CASE WHEN d.pctChg > 0 THEN 1 ELSE 0 END) AS rising_count,
      SUM(CASE WHEN d.pctChg < 0 THEN 1 ELSE 0 END) AS falling_count,
      AVG(d.close) AS avg_close,
      MAX(d.close) AS max_close,
      MIN(d.close) AS min_close
    FROM stock_daily d
    JOIN stock_industry i ON d.code = i.code
    WHERE d.adjustflag = 3
      AND d.date >= %s AND d.date <= %s
      AND i.industry IS NOT NULL AND i.industry != ''
    GROUP BY d.date, i.industry
    ON DUPLICATE KEY UPDATE
      stock_count = VALUES(stock_count),
      avg_pct_chg = VALUES(avg_pct_chg),
      total_amount = VALUES(total_amount),
      total_volume = VALUES(total_volume),
      avg_turn = VALUES(avg_turn),
      rising_count = VALUES(rising_count),
      falling_count = VALUES(falling_count),
      avg_close = VALUES(avg_close),
      max_close = VALUES(max_close),
      min_close = VALUES(min_close)
    """

    with conn.cursor() as cursor:
        cursor.execute(create_table_sql)
        try:
            cursor.execute("CREATE INDEX idx_code ON stock_industry(code)")
        except pymysql.MySQLError as e:
            if "Duplicate" in str(e) or "already exists" in str(e).lower():
                pass
            else:
                raise

        # 找出 [start, end] 區間內尚未聚合的日期範圍
        cursor.execute(
            """
            SELECT MIN(d.date), MAX(d.date)
            FROM stock_daily d
            WHERE d.adjustflag = 3
              AND d.date >= %s AND d.date <= %s
              AND NOT EXISTS (
                SELECT 1 FROM industry_daily id WHERE id.date = d.date LIMIT 1
              )
            """,
            (start, end),
        )
        min_missing, max_missing = cursor.fetchone()

        if min_missing is None or max_missing is None:
            print(f"[skip] 行業日聚合數據已是最新（{start} ~ {end}）")
            return 0

        cursor.execute(agg_sql, (min_missing, max_missing))
        conn.commit()
        affected = cursor.rowcount
    print(f"[done] 行業日聚合數據已同步 {affected} 條（{min_missing} ~ {max_missing}）")
    return affected
