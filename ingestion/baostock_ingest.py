"""Baostock 日线数据采集脚本（增量更新版）— 入口 / 菜單 / CLI 調度層。

沿用原项目 MCP/scripts/getDataScripts/获取日线数据.py 的增量更新逻辑：
- 使用静态股票清单 stock_list.json（3354 只实际股票），而非 query_all_stock()（7333 个含指数/停牌）
- 每只股票先查数据库最新日期，只拉取缺失部分，避免全量重复拉取
- 支持 3 种复权（1后复权/2前复权/3不复权）+ 沪深指数
- 支持命令行参数（后端 SyncService 调用）和交互式菜单（用户直接运行）

P5 三模塊重構：本文件僅保留入口/菜單/CLI 調度與同步編排邏輯，
Baostock API 調用層見 baostock_fetch.py，資料庫寫入層見 baostock_write.py。

用法:
    # 命令行模式（后端调用）
    python ingestion/baostock_ingest.py --help
    python ingestion/baostock_ingest.py --mode incremental --adjustflag 3
    python ingestion/baostock_ingest.py --mode incremental --adjustflags 1,2,3 --index
    python ingestion/baostock_ingest.py --mode range --start 2026-08-17 --end 2026-08-17 --adjustflags 1,2,3 --index
    python ingestion/baostock_ingest.py --mode range --codes sh.600000,sz.000001 --start 2026-08-01 --end 2026-08-17 --adjustflag 3
    # --progress-json：機器可解析的 JSON 進度協議（供 Java SyncService 精確解析進度）
    python ingestion/baostock_ingest.py --mode incremental --adjustflags 1,2,3 --index --progress-json

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
from datetime import date, timedelta
from pathlib import Path

# 確保 stdout/stderr 用 UTF-8 輸出，避免 Windows GBK 編碼導致後端正則匹配失敗
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 確保同目錄模塊可被 import（直接以腳本方式運行時 sys.path[0] 已是本目錄，
# 但被作為包導入或從其他工作目錄運行時需要顯式補上）
_INGESTION_DIR = Path(__file__).resolve().parent
if str(_INGESTION_DIR) not in sys.path:
    sys.path.insert(0, str(_INGESTION_DIR))

# P5 三模塊重構：從拆分後的子模塊導入全部公開符號
# - baostock_fetch: Baostock API 調用層（login / fetch / 清單載入 / 解析）
# - baostock_write: 資料庫寫入層（connect / upsert / 增量查詢 / 聚合）
from baostock_fetch import *  # noqa: F401,F403  (重新導出供本模塊及下游使用)
from baostock_write import *  # noqa: F401,F403

# 顯式導入常用符號，便於靜態分析與可讀性
from baostock_fetch import (
    ADJUSTFLAG_MAP,
    _ensure_login,
    _fetch_index,
    _fetch_stock,
    _load_index_list,
    _load_stock_list,
    _login_baostock,
    bs,
)
from baostock_write import (
    _connect,
    _get_existing_indexes,
    _get_existing_stocks,
    _get_index_last_date,
    _get_industry_last_update_date,
    _get_stock_last_date,
    _load_env,
    _sync_index_metadata,
    _sync_industry_daily,
    _upsert_index_batch,
    _upsert_industry_batch,
    _upsert_stock_batch,
)

# 全局：--progress-json 模式開關
# 啟用後，機器可解析的 JSON 進度行輸出到 stdout，人類可讀的中文進度輸出到 stderr
_PROGRESS_JSON = False


def _emit_progress_json(obj: dict) -> None:
    """輸出一行 JSON 到 stdout（僅 --progress-json 模式）。"""
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def _log(msg: str, *, flush: bool = False) -> None:
    """統一日誌輸出：progress-json 模式時走 stderr，否則走 stdout（保持兼容）。"""
    stream = sys.stderr if _PROGRESS_JSON else sys.stdout
    print(msg, file=stream, flush=flush)


# ============================================================================
# 同步編排邏輯（調用 fetch 層拉取 + write 層寫入）
# ============================================================================

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
    failed = 0
    batch: list[tuple] = []
    total_codes = len(codes)

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

        try:
            for row in _fetch_stock(code, stock_start, end, adjustflag):
                batch.append(row)
                if len(batch) >= batch_size:
                    _upsert_stock_batch(cursor, batch)
                    conn.commit()
                    total += len(batch)
                    batch.clear()
                    _log(f"[info] {ADJUSTFLAG_MAP[adjustflag]} 已寫入 {total} 條", flush=True)
                    if _PROGRESS_JSON:
                        _emit_progress_json({
                            "type": "progress",
                            "total": total_codes,
                            "completed": i + 1,
                            "failed": failed,
                            "current_code": code,
                            "phase": "stock_daily",
                            "adjustflag": adjustflag,
                        })
        except Exception as e:
            failed += 1
            if _PROGRESS_JSON:
                _emit_progress_json({
                    "type": "error",
                    "code": code,
                    "message": str(e),
                })
            _log(f"[error] {code} 拉取失敗: {e}", flush=True)
            continue

        # 每處理 100 隻股票打印進度
        if (i + 1) % 100 == 0:
            _log(f"[info] 進度: {i + 1}/{total_codes} 隻股票（{ADJUSTFLAG_MAP[adjustflag]}）", flush=True)
            if _PROGRESS_JSON:
                _emit_progress_json({
                    "type": "progress",
                    "total": total_codes,
                    "completed": i + 1,
                    "failed": failed,
                    "current_code": code,
                    "phase": "stock_daily",
                    "adjustflag": adjustflag,
                })

        # 拉取限頻：每隻股票之間短暫暫停，避免連續請求觸發 Baostock 限流
        time.sleep(0.1)

    if batch:
        _upsert_stock_batch(cursor, batch)
        conn.commit()
        total += len(batch)

    cursor.close()
    if incremental and skipped > 0:
        _log(f"[info] {ADJUSTFLAG_MAP[adjustflag]} 跳過 {skipped} 隻已是最新數據的股票")
    _log(f"[done] {ADJUSTFLAG_MAP[adjustflag]} 股票日線共寫入 {total} 條")
    if _PROGRESS_JSON:
        _emit_progress_json({
            "type": "done",
            "total_written": total,
            "total_failed": failed,
        })
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
    failed = 0
    batch: list[tuple] = []
    total_codes = len(codes)

    for i, code in enumerate(codes):
        if incremental:
            last_date = _get_index_last_date(conn, code, "d")
            if last_date is not None:
                idx_start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                if idx_start > end:
                    _log(f"[info] 指數 {code} 已是最新，跳過")
                    continue
            else:
                idx_start = start
        else:
            idx_start = start

        try:
            for row in _fetch_index(code, idx_start, end):
                batch.append(row)
                if len(batch) >= 100:
                    _upsert_index_batch(cursor, batch)
                    conn.commit()
                    total += len(batch)
                    batch.clear()
                    _log(f"[info] 指數已寫入 {total} 條", flush=True)
                    if _PROGRESS_JSON:
                        _emit_progress_json({
                            "type": "progress",
                            "total": total_codes,
                            "completed": i + 1,
                            "failed": failed,
                            "current_code": code,
                            "phase": "index_daily",
                            "adjustflag": 0,
                        })
        except Exception as e:
            failed += 1
            if _PROGRESS_JSON:
                _emit_progress_json({
                    "type": "error",
                    "code": code,
                    "message": str(e),
                })
            _log(f"[error] 指數 {code} 拉取失敗: {e}", flush=True)
            continue

        # 拉取限頻：每個指數之間短暫暫停
        time.sleep(0.2)

    if batch:
        _upsert_index_batch(cursor, batch)
        conn.commit()
        total += len(batch)

    cursor.close()
    _log(f"[done] 指數日線共寫入 {total} 條")
    if _PROGRESS_JSON:
        _emit_progress_json({
            "type": "done",
            "total_written": total,
            "total_failed": failed,
        })
    return total


# ============================================================================
# 命令行模式
# ============================================================================

def _run_cli(args) -> int:
    """命令行模式入口。"""
    global _PROGRESS_JSON
    _PROGRESS_JSON = getattr(args, "progress_json", False)

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
            _log(f"[info] 增量更新模式：從資料庫獲取 {len(codes)} 隻股票")
        else:
            codes = _load_stock_list()
            _log(f"[info] 範圍模式：從清單載入 {len(codes)} 隻股票")

    # 確定指數清單
    index_codes = _load_index_list() if args.index else []

    _log(f"[info] 日期範圍: {start_date} ~ {end_date}")
    _log(f"[info] 復權類型: {[ADJUSTFLAG_MAP[af] for af in adjustflags]}")
    if index_codes:
        _log(f"[info] 指數清單: {len(index_codes)} 個指數（10 大類別）")

    conn = _connect()
    try:
        # 同步指數元數據（分類/名稱）到 index_metadata 表
        if args.index:
            _sync_index_metadata(conn)

        grand_total = 0
        for af in adjustflags:
            # P4-1: 前復權全量重刷——除權除息後 Baostock 重算全部歷史，增量模式會導致陳舊失真
            af_incremental = incremental
            af_start = start_date
            if af == 2 and getattr(args, 'full_refresh_adjustflag2', False):
                af_incremental = False
                af_start = os.getenv("SYNC_DEFAULT_START_DATE", "2021-01-01")
                _log(f"\n[WARNING] 前復權全量重刷模式：從 {af_start} 重新拉取全部歷史數據")
                _log(f"[WARNING] 這是因為前復權價格在除權除息後會被 Baostock 重算，")
                _log(f"[WARNING] 增量模式只拉 max_date+1 之後的數據，歷史數據會逐漸陳舊失真。")
                _log(f"[WARNING] 建議每季度至少執行一次：python baostock_ingest.py --full-refresh-adjustflag2 --adjustflags 2")
            _log(f"\n{'=' * 60}")
            _log(f"開始同步 {ADJUSTFLAG_MAP[af]} 股票日線數據")
            _log(f"{'=' * 60}")
            grand_total += _sync_stocks(
                conn, codes, af, af_start, end_date, args.batch_size, af_incremental
            )

        if index_codes:
            _log(f"\n{'=' * 60}")
            _log(f"開始同步指數日線數據（{len(index_codes)} 個指數）")
            _log(f"{'=' * 60}")
            grand_total += _sync_indexes(conn, index_codes, start_date, end_date, incremental)

        if args.industry:
            _log(f"\n{'=' * 60}")
            _log(f"開始同步行業分類數據")
            _log(f"{'=' * 60}")
            grand_total += _sync_industry(conn, force=args.force_industry)

        _log(f"\n{'=' * 60}")
        _log(f"全部完成！共寫入 {grand_total} 條記錄")
        _log(f"{'=' * 60}")
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
    print(" 14. 發現並驗證 Baostock 指數清單（更新 index_list.json）")
    print("=" * 60)

    while True:
        choice = input("\n請輸入選項 (1-14): ").strip()
        if choice in [str(i) for i in range(1, 15)]:
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
    elif choice == 14:
        import subprocess
        import sys

        print("\n[info] 正在調用 discover_indices.py 發現並驗證指數，預計 2-3 分鐘...")
        script = Path(__file__).resolve().parent / "discover_indices.py"
        try:
            subprocess.run([sys.executable, str(script), "--sample", "--delay", "0.2", "--output", "ingestion/index_list.json"], check=True)
            print("[info] 指數清單已更新，請重新運行同步選項以拉取指數數據。")
        except subprocess.CalledProcessError as e:
            print(f"[error] 指數發現失敗: {e}", file=sys.stderr)
        return {"incremental": False, "adjustflags": [], "index": False, "industry": False, "discover_only": True}

    return config


def _run_interactive() -> int:
    """交互式模式入口。"""
    _load_env(Path(__file__).resolve().parent.parent)
    config = _show_menu()

    if config.get("discover_only"):
        return 0

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

        # 行業日聚合：同步了不復權股票日線時，用最新行業分類做 (date, industry) 聚合
        if 3 in adjustflags:
            print(f"\n{'=' * 60}")
            print(f"開始同步行業日聚合數據")
            print(f"{'=' * 60}")
            grand_total += _sync_industry_daily(conn, start_date, end_date)

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
    parser.add_argument("--full-refresh-adjustflag2", action="store_true",
                        help="全量重刷前復權(adjustflag=2)歷史數據——解決前復權增量陳舊化問題"
                             "（除權除息後 Baostock 會重算全部歷史價，增量模式只拉 max_date+1 會導致數據失真）")
    parser.add_argument("--progress-json", action="store_true",
                        help="啟用 JSON 進度協議：每次寫入批次時輸出一行 JSON 到 stdout，"
                             "中文進度信息改為 stderr。供 Java SyncService 精確解析進度。"
                             "JSON 行格式：{\"type\":\"progress\",...} / {\"type\":\"done\",...} / {\"type\":\"error\",...}")
    args = parser.parse_args()

    return _run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
