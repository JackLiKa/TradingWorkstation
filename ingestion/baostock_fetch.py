"""Baostock API 調用層 — 登錄、股票/指數日線拉取、清單載入與數據解析。

從 baostock_ingest.py 拆分而來（P5 三模塊重構），職責：
- Baostock 會話管理（login / ensure_login / 重試）
- query_history_k_data_plus 股票與指數日線拉取
- 靜態清單載入（stock_list.json / index_list.json）
- 原始字符串 → Decimal/int 解析輔助

本模塊僅依賴 baostock 庫與標準庫，不涉及資料庫寫入。
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import baostock as bs

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
# 數據解析輔助
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


# ============================================================================
# 靜態清單載入
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
# 數據拉取
# ============================================================================

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
