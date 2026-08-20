"""Baostock 日线数据采集脚本（增量更新版）。

沿用原项目 MCP/scripts/getDataScripts/获取日线数据.py 的增量更新逻辑：
- 使用静态股票清单 stock_list.json（3354 只实际股票），而非 query_all_stock()（7333 个含指数/停牌）
- 每只股票先查数据库最新日期，只拉取缺失部分，避免全量重复拉取
- 支持 3 种复权（1后复权/2前复权/3不复权）+ 沪深指数
- 支持命令行参数（后端 SyncService 调用）和交互式菜单（用户直接运行）

用法:
    # 命令行模式（后端调用）
    python ingestion/baostock_ingest.py --help
    python ingestion/baostock_ingest.py --mode incremental --adjustflag 3
    python ingestion/baostock_ingest.py --mode incremental --adjustflags 1,2,3 --index
    python ingestion/baostock_ingest.py --mode range --start 2026-08-17 --end 2026-08-17 --adjustflags 1,2,3 --index
    python ingestion/baostock_ingest.py --mode range --codes sh.600000,sz.000001 --start 2026-08-01 --end 2026-08-17 --adjustflag 3

    # 交互式模式（用户直接运行，无参数时自动进入）
    python ingestion/baostock_ingest.py

依赖: pip install baostock pymysql
环境变量: DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD/DB_CHARSET (从根 .env 读取)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Iterable

# 確保 stdout/stderr 用 UTF-8 輸出，避免 Windows GBK 編碼導致後端正則匹配失敗
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import baostock as bs
import pymysql

# 股票日線欄位
FIELDS = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
# 指數日線欄位
INDEX_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,pctChg"

# 預設指數清單（與數據庫 index_daily 表一致）
DEFAULT_INDEX_CODES = [
    "sh.000001",  # 上證綜指
    "sh.000016",  # 上證50
    "sh.000300",  # 滬深300
    "sh.000852",  # 中證1000
    "sh.000905",  # 中證500
    "sz.399001",  # 深證成指
    "sz.399005",  # 中小100
    "sz.399006",  # 創業板指
]

ADJUSTFLAG_MAP = {1: "後復權", 2: "前復權", 3: "不復權"}


# ============================================================================
# 環境與資料庫
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
# 股票清單
# ============================================================================

def _load_stock_list() -> list[str]:
    """從 stock_list.json 載入股票清單。"""
    list_path = Path(__file__).resolve().parent / "stock_list.json"
    if not list_path.exists():
        raise FileNotFoundError(f"找不到股票清單: {list_path}")
    data = json.loads(list_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("stocks", [])
    return data


def _load_index_list() -> list[str]:
    """從 index_list.json 載入指數清單，沒有則用預設清單。

    支持兩種格式：
    1. 舊格式（list[str]）：["sh.000001", "sz.399001", ...]
    2. 新格式（dict with categories）：
       {"categories": [{"category": "綜合指數", "indices": [{"code": "sh.000001", "name": "上證綜指"}, ...]}]}
    """
    list_path = Path(__file__).resolve().parent / "index_list.json"
    if not list_path.exists():
        return DEFAULT_INDEX_CODES
    data = json.loads(list_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    # 新格式：從 categories 中提取所有代碼
    if "categories" in data:
        codes = []
        for cat in data["categories"]:
            for idx in cat.get("indices", []):
                codes.append(idx["code"])
        return codes if codes else DEFAULT_INDEX_CODES
    return data.get("indexes", data.get("indices", DEFAULT_INDEX_CODES))


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


# ============================================================================
# 資料庫查詢（增量更新核心）
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
# Baostock 登錄管理
# ============================================================================

def _login_baostock(max_retries: int = 3) -> bool:
    """登入 Baostock，支持重試。"""
    for attempt in range(max_retries):
        try:
            lg = bs.login()
            if lg.error_code == "0":
                return True
            print(f"[warn] baostock 登錄失敗 (嘗試 {attempt + 1}/{max_retries}): {lg.error_msg}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(3)
        except Exception as e:
            print(f"[warn] baostock 登錄異常 (嘗試 {attempt + 1}/{max_retries}): {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(3)
    return False


def _ensure_login() -> None:
    """檢查 Baostock 登錄狀態，必要時重新登錄。"""
    rs = bs.query_all_stock(day=datetime.now().strftime("%Y-%m-%d"))
    if rs.error_code != "0":
        try:
            bs.logout()
        except Exception:
            pass
        if not _login_baostock():
            raise RuntimeError("baostock 重新登錄失敗")


# ============================================================================
# 數據拉取與寫入
# ============================================================================

def _to_decimal(value: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except Exception:
        return None


def _to_int(value: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


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
        "industry_classification=VALUES(industry_classification), updated_at=CURRENT_TIMESTAMP"
    )
    cursor.executemany(sql, rows)


def _get_industry_last_update_date(conn):
    """獲取 stock_industry 表中最新的 update_date。"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT MAX(update_date) FROM stock_industry")
        result = cursor.fetchone()
        return result[0] if result and result[0] else None


def _sync_industry(conn, *, force: bool = False) -> int:
    """同步行業分類數據（baostock 每週一更新，數據量小）。

    Args:
        conn: 資料庫連接。
        force: True 時強制全量拉取（忽略新鮮度檢查）；
               False 時若 DB 最新 update_date 距今天 ≤7 天則跳過拉取，
               避免每次運行都重複下載 5542 行未變化的數據。
    """
    if not force:
        last_update = _get_industry_last_update_date(conn)
        if last_update is not None:
            age_days = (date.today() - last_update).days
            if age_days < 7:
                print(
                    f"[skip] 行業數據已是最新（update_date={last_update}, 距今 {age_days} 天），"
                    f"baostock 每週一更新，跳過本次拉取（使用 --force-industry 可強制刷新）"
                )
                return 0

    _ensure_login()
    rs = bs.query_stock_industry()
    if rs.error_code != "0":
        print(f"[error] query_stock_industry 失敗: {rs.error_msg}")
        return 0

    rows = []
    while rs.next():
        data = rs.get_row_data()
        # fields: updateDate, code, code_name, industry, industryClassification
        code = data[1]
        update_date = data[0]
        code_name = data[2] or None
        industry = data[3] or None
        industry_class = data[4] or None
        rows.append((code, update_date, code_name, industry, industry_class))

    if not rows:
        print("[done] 行業數據無記錄")
        return 0

    cursor = conn.cursor()
    _upsert_industry_batch(cursor, rows)
    conn.commit()
    cursor.close()
    print(f"[done] 行業數據共寫入 {len(rows)} 條")
    return len(rows)


def _fetch_stock(code: str, start: str, end: str, adjustflag: int) -> Iterable[tuple]:
    """從 Baostock 獲取股票日線數據。"""
    rs = bs.query_history_k_data_plus(
        code, FIELDS, start_date=start, end_date=end, frequency="d", adjustflag=str(adjustflag)
    )
    if rs.error_code != "0":
        if "用户未登" in rs.error_msg or "未登錄" in rs.error_msg:
            _ensure_login()
            rs = bs.query_history_k_data_plus(
                code, FIELDS, start_date=start, end_date=end, frequency="d", adjustflag=str(adjustflag)
            )
        if rs.error_code != "0":
            print(f"[warn] {code}: {rs.error_msg}", file=sys.stderr)
            return
    while rs.next():
        row = rs.get_row_data()
        yield (
            row[1], row[0],  # code, date
            _to_decimal(row[2]), _to_decimal(row[3]), _to_decimal(row[4]), _to_decimal(row[5]),
            _to_decimal(row[6]), _to_int(row[7]), _to_decimal(row[8]),
            int(float(row[9])) if row[9] else adjustflag,
            _to_decimal(row[10]),
            int(float(row[11])) if row[11] else 1,
            _to_decimal(row[12]),
            int(float(row[13])) if row[13] else 0,
        )


def _fetch_index(code: str, start: str, end: str) -> Iterable[tuple]:
    """從 Baostock 獲取指數日線數據。"""
    rs = bs.query_history_k_data_plus(
        code, INDEX_FIELDS, start_date=start, end_date=end, frequency="d"
    )
    if rs.error_code != "0":
        if "用户未登" in rs.error_msg or "未登錄" in rs.error_msg:
            _ensure_login()
            rs = bs.query_history_k_data_plus(
                code, INDEX_FIELDS, start_date=start, end_date=end, frequency="d"
            )
        if rs.error_code != "0":
            print(f"[warn] index {code}: {rs.error_msg}", file=sys.stderr)
            return
    while rs.next():
        row = rs.get_row_data()
        yield (
            row[1], row[0],  # code, date
            _to_decimal(row[2]), _to_decimal(row[3]), _to_decimal(row[4]), _to_decimal(row[5]),
            _to_decimal(row[6]), _to_int(row[7]), _to_decimal(row[8]),
            _to_decimal(row[9]),
        )


# ============================================================================
# 同步邏輯
# ============================================================================

def _sync_stocks(
    conn,
    codes: list[str],
    adjustflag: int,
    start: str,
    end: str,
    batch_size: int,
    incremental: bool,
) -> int:
    """同步股票日線數據，返回寫入條數。"""
    cursor = conn.cursor()
    total = 0
    skipped = 0
    batch: list[tuple] = []

    for i, code in enumerate(codes):
        # 增量模式：計算每隻股票的實際拉取起始日期
        if incremental:
            last_date = _get_stock_last_date(conn, code, adjustflag)
            if last_date is not None:
                stock_start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                if stock_start > end:
                    skipped += 1
                    continue
            else:
                stock_start = start
        else:
            stock_start = start

        for row in _fetch_stock(code, stock_start, end, adjustflag):
            batch.append(row)
            if len(batch) >= batch_size:
                _upsert_stock_batch(cursor, batch)
                conn.commit()
                total += len(batch)
                batch.clear()
                print(f"[info] {ADJUSTFLAG_MAP[adjustflag]} 已寫入 {total} 條", flush=True)

        # 每處理 100 隻股票打印進度
        if (i + 1) % 100 == 0:
            print(f"[info] 進度: {i + 1}/{len(codes)} 隻股票（{ADJUSTFLAG_MAP[adjustflag]}）", flush=True)

    if batch:
        _upsert_stock_batch(cursor, batch)
        conn.commit()
        total += len(batch)

    cursor.close()
    if incremental and skipped > 0:
        print(f"[info] {ADJUSTFLAG_MAP[adjustflag]} 跳過 {skipped} 隻已是最新數據的股票")
    print(f"[done] {ADJUSTFLAG_MAP[adjustflag]} 股票日線共寫入 {total} 條")
    return total


def _sync_indexes(
    conn,
    codes: list[str],
    start: str,
    end: str,
    incremental: bool,
) -> int:
    """同步指數日線數據，返回寫入條數。"""
    cursor = conn.cursor()
    total = 0
    batch: list[tuple] = []

    for code in codes:
        if incremental:
            last_date = _get_index_last_date(conn, code, "d")
            if last_date is not None:
                idx_start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                if idx_start > end:
                    print(f"[info] 指數 {code} 已是最新，跳過")
                    continue
            else:
                idx_start = start
        else:
            idx_start = start

        for row in _fetch_index(code, idx_start, end):
            batch.append(row)
            if len(batch) >= 100:
                _upsert_index_batch(cursor, batch)
                conn.commit()
                total += len(batch)
                batch.clear()
                print(f"[info] 指數已寫入 {total} 條", flush=True)

    if batch:
        _upsert_index_batch(cursor, batch)
        conn.commit()
        total += len(batch)

    cursor.close()
    print(f"[done] 指數日線共寫入 {total} 條")
    return total


# ============================================================================
# 命令行模式
# ============================================================================

def _run_cli(args) -> int:
    """命令行模式入口。"""
    _load_env(Path(__file__).resolve().parent.parent)

    if not _login_baostock():
        print("[error] baostock 登錄失敗", file=sys.stderr)
        return 1

    # 解析 adjustflags 參數
    if args.adjustflags:
        adjustflags = [int(x.strip()) for x in args.adjustflags.split(",") if x.strip()]
    else:
        adjustflags = [int(args.adjustflag)]

    # 確定日期範圍
    end_date = args.end or date.today().isoformat()
    start_date = args.start or os.getenv("SYNC_DEFAULT_START_DATE", "2021-01-01")
    incremental = args.mode == "incremental"

    # 確定股票清單（僅當需要同步股票日線時才載入）
    codes: list[str] = []
    if adjustflags:
        if args.codes:
            codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        elif incremental:
            # 增量模式：用資料庫中已有的股票
            conn = _connect()
            try:
                codes = _get_existing_stocks(conn, adjustflags[0])
            finally:
                conn.close()
            if not codes:
                # 資料庫沒有數據，用靜態清單
                codes = _load_stock_list()
            print(f"[info] 增量更新模式：從資料庫獲取 {len(codes)} 隻股票")
        else:
            codes = _load_stock_list()
            print(f"[info] 範圍模式：從清單載入 {len(codes)} 隻股票")

    # 確定指數清單
    index_codes = _load_index_list() if args.index else []

    print(f"[info] 日期範圍: {start_date} ~ {end_date}")
    print(f"[info] 復權類型: {[ADJUSTFLAG_MAP[af] for af in adjustflags]}")
    if index_codes:
        print(f"[info] 指數清單: {len(index_codes)} 個指數（10 大類別）")

    conn = _connect()
    try:
        # 同步指數元數據（分類/名稱）到 index_metadata 表
        if args.index:
            _sync_index_metadata(conn)

        grand_total = 0
        for af in adjustflags:
            print(f"\n{'=' * 60}")
            print(f"開始同步 {ADJUSTFLAG_MAP[af]} 股票日線數據")
            print(f"{'=' * 60}")
            grand_total += _sync_stocks(
                conn, codes, af, start_date, end_date, args.batch_size, incremental
            )

        if index_codes:
            print(f"\n{'=' * 60}")
            print(f"開始同步指數日線數據（{len(index_codes)} 個指數）")
            print(f"{'=' * 60}")
            grand_total += _sync_indexes(conn, index_codes, start_date, end_date, incremental)

        if args.industry:
            print(f"\n{'=' * 60}")
            print(f"開始同步行業分類數據")
            print(f"{'=' * 60}")
            grand_total += _sync_industry(conn, force=args.force_industry)

        print(f"\n{'=' * 60}")
        print(f"全部完成！共寫入 {grand_total} 條記錄")
        print(f"{'=' * 60}")
    finally:
        conn.close()
        try:
            bs.logout()
        except Exception:
            pass

    return 0


# ============================================================================
# 交互式模式
# ============================================================================

def _show_menu() -> dict:
    """顯示交互式菜單，返回選項配置。"""
    print("\n" + "=" * 60)
    print("A 股日線數據採集（增量更新版）")
    print("=" * 60)
    print("請選擇功能：")
    print("  1. 獲取歷史後復權數據（2021-01-01 至今）")
    print("  2. 獲取歷史前復權數據（2021-01-01 至今）")
    print("  3. 獲取歷史不復權數據（2021-01-01 至今）")
    print("  4. 獲取歷史全部三種復權數據（2021-01-01 至今）")
    print("  5. 增量更新後復權數據")
    print("  6. 增量更新前復權數據")
    print("  7. 增量更新不復權數據")
    print("  8. 增量更新全部三種復權數據")
    print("  9. 獲取滬深指數歷史數據（2021-01-01 至今）")
    print(" 10. 增量更新滬深指數數據")
    print(" 11. 增量更新全部（三種復權 + 指數 + 行業）")
    print(" 12. 指定日期範圍 + 全部三種復權 + 指數 + 行業")
    print(" 13. 僅同步行業分類數據")
    print("=" * 60)

    while True:
        choice = input("\n請輸入選項 (1-13): ").strip()
        if choice in [str(i) for i in range(1, 14)]:
            choice = int(choice)
            break
        print("無效選項，請重新輸入！")

    config = {"incremental": False, "adjustflags": [], "index": False, "industry": False}

    if choice == 1:
        config["adjustflags"] = [1]
    elif choice == 2:
        config["adjustflags"] = [2]
    elif choice == 3:
        config["adjustflags"] = [3]
    elif choice == 4:
        config["adjustflags"] = [1, 2, 3]
    elif choice == 5:
        config["adjustflags"] = [1]; config["incremental"] = True
    elif choice == 6:
        config["adjustflags"] = [2]; config["incremental"] = True
    elif choice == 7:
        config["adjustflags"] = [3]; config["incremental"] = True
    elif choice == 8:
        config["adjustflags"] = [1, 2, 3]; config["incremental"] = True
    elif choice == 9:
        config["adjustflags"] = []; config["index"] = True
    elif choice == 10:
        config["adjustflags"] = []; config["index"] = True; config["incremental"] = True
    elif choice == 11:
        config["adjustflags"] = [1, 2, 3]; config["index"] = True; config["industry"] = True; config["incremental"] = True
    elif choice == 12:
        config["adjustflags"] = [1, 2, 3]; config["index"] = True; config["industry"] = True
        config["start"] = input("請輸入開始日期 (YYYY-MM-DD): ").strip()
        config["end"] = input("請輸入結束日期 (YYYY-MM-DD，回車=今天): ").strip() or date.today().isoformat()
    elif choice == 13:
        config["adjustflags"] = []; config["industry"] = True

    return config


def _run_interactive() -> int:
    """交互式模式入口。"""
    _load_env(Path(__file__).resolve().parent.parent)
    config = _show_menu()

    incremental = config["incremental"]
    adjustflags = config["adjustflags"]
    do_index = config["index"]
    do_industry = config["industry"]
    start_date = config.get("start", "2021-01-01")
    end_date = config.get("end", date.today().isoformat())

    print(f"\n配置：")
    print(f"  模式: {'增量更新' if incremental else '歷史獲取'}")
    print(f"  復權: {[ADJUSTFLAG_MAP[af] for af in adjustflags] if adjustflags else '無'}")
    print(f"  指數: {'是' if do_index else '否'}")
    print(f"  行業: {'是' if do_industry else '否'}")
    print(f"  日期: {start_date} ~ {end_date}")

    if not _login_baostock():
        print("[error] baostock 登錄失敗", file=sys.stderr)
        return 1

    conn = _connect()
    try:
        grand_total = 0

        # 股票同步
        if adjustflags:
            if incremental:
                codes = _get_existing_stocks(conn, adjustflags[0])
                if not codes:
                    codes = _load_stock_list()
                print(f"\n增量更新：從資料庫獲取 {len(codes)} 隻股票")
            else:
                codes = _load_stock_list()
                print(f"\n歷史獲取：從清單載入 {len(codes)} 隻股票")

            for af in adjustflags:
                print(f"\n{'=' * 60}")
                print(f"開始同步 {ADJUSTFLAG_MAP[af]} 股票日線數據")
                print(f"{'=' * 60}")
                grand_total += _sync_stocks(
                    conn, codes, af, start_date, end_date,
                    int(os.getenv("SYNC_BATCH_SIZE", "1000")), incremental
                )

        # 指數同步
        if do_index:
            # 先同步指數元數據（分類/名稱）到 index_metadata 表
            _sync_index_metadata(conn)

            if incremental:
                index_codes = _get_existing_indexes(conn, "d")
                if not index_codes:
                    index_codes = _load_index_list()
            else:
                index_codes = _load_index_list()

            print(f"\n{'=' * 60}")
            print(f"開始同步指數日線數據（{len(index_codes)} 個指數，10 大類別）")
            print(f"{'=' * 60}")
            grand_total += _sync_indexes(conn, index_codes, start_date, end_date, incremental)

        # 行業同步
        if do_industry:
            print(f"\n{'=' * 60}")
            print(f"開始同步行業分類數據")
            print(f"{'=' * 60}")
            grand_total += _sync_industry(conn, force=False)

        print(f"\n{'=' * 60}")
        print(f"全部完成！共寫入 {grand_total} 條記錄")
        print(f"{'=' * 60}")
    finally:
        conn.close()
        try:
            bs.logout()
        except Exception:
            pass

    return 0


# ============================================================================
# 主入口
# ============================================================================

def main() -> int:
    # 無參數時進入交互式模式
    if len(sys.argv) <= 1:
        return _run_interactive()

    # 有參數時用命令行模式
    parser = argparse.ArgumentParser(description="Baostock 日線數據採集（增量更新版）")
    parser.add_argument("--mode", default="incremental", choices=["incremental", "range"],
                        help="incremental=增量更新（只拉缺失數據），range=指定日期範圍全量拉取")
    parser.add_argument("--adjustflag", default="3", choices=["1", "2", "3"],
                        help="單個復權類型：1後復權 2前復權 3不復權（與 --adjustflags 互斥）")
    parser.add_argument("--adjustflags", default="",
                        help="多個復權類型，逗號分隔，如 1,2,3（優先於 --adjustflag）")
    parser.add_argument("--start", default="", help="起始日期 YYYY-MM-DD（incremental 模式可省略）")
    parser.add_argument("--end", default="", help="結束日期 YYYY-MM-DD（默認今天）")
    parser.add_argument("--codes", default="", help="逗號分隔股票代碼，為空則用股票清單")
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("SYNC_BATCH_SIZE", "1000")))
    parser.add_argument("--index", action="store_true", help="同時同步指數數據到 index_daily 表")
    parser.add_argument("--industry", action="store_true", help="同時同步行業分類數據到 stock_industry 表")
    parser.add_argument("--force-industry", action="store_true",
                        help="強制全量拉取行業數據（忽略 7 天新鮮度檢查）")
    args = parser.parse_args()

    return _run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
