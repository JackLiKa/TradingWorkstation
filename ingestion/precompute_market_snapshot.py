"""行情預計算腳本 — 在數據更新完成後計算行情分析快照，持久化到 market_analysis_snapshot 表。

設計目標：
- 在 ingestion 完成後自動觸發，預計算行情分析數據
- 結果寫入 market_analysis_snapshot 表，前端直接加載快照
- 消除前端「每次加載行情分析都要等很久」的問題
- 歷史快照可追蹤，支持回看某天的市場狀態

預計算內容：
1. 市場概覽（指數漲跌、成交額、漲跌家數）
2. 行業景氣度排名（動量/資金/活躍度/廣度 4 維度評分）
3. 行業輪動信號（短期 vs 長期動量對比）
4. 市場廣度（漲跌家數、漲停跌停）
5. 數據範圍元信息

用法：
    # 獨立執行（計算最新交易日的快照）
    python ingestion/precompute_market_snapshot.py

    # 指定交易日
    python ingestion/precompute_market_snapshot.py --date 2026-08-24

    # 由 baostock_ingest.py 自動調用（--auto 模式，失敗不阻塞）
    python ingestion/precompute_market_snapshot.py --auto
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# UTF-8 輸出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 確保同目錄模塊可被 import
_INGESTION_DIR = Path(__file__).resolve().parent
if str(_INGESTION_DIR) not in sys.path:
    sys.path.insert(0, str(_INGESTION_DIR))

import pymysql

logger = logging.getLogger("precompute")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _load_env(root: Path) -> None:
    """從 .env 加載環境變量。"""
    env_file = root / ".env"
    if not env_file.exists():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                os.environ.setdefault(k, v)


def _connect() -> pymysql.Connection:
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "a_stock_baostock"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        read_timeout=180,
        connect_timeout=10,
    )


def _ensure_snapshot_table(conn) -> None:
    """確保 market_analysis_snapshot 表存在。"""
    ddl = """
    CREATE TABLE IF NOT EXISTS market_analysis_snapshot (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        trade_date DATE NOT NULL,
        snapshot_type VARCHAR(50) NOT NULL COMMENT 'market_overview/industry_prosperity/rotation_signals/market_breadth',
        snapshot_data JSON NOT NULL COMMENT '預計算的 JSON 快照數據',
        computed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        data_version VARCHAR(20) NOT NULL DEFAULT '1.0' COMMENT '快照格式版本',
        UNIQUE KEY uk_date_type (trade_date, snapshot_type),
        INDEX idx_trade_date (trade_date),
        INDEX idx_computed_at (computed_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行情分析預計算快照'
    """
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    logger.info("[預計算] 確保 market_analysis_snapshot 表存在")


def _get_latest_trade_date(conn) -> str | None:
    """獲取最新交易日。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT date FROM stock_daily WHERE adjustflag = 3 "
            "ORDER BY date DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            return str(row["date"])
    return None


def _compute_market_overview(conn, trade_date: str) -> dict:
    """計算市場概覽快照。"""
    overview = {"trade_date": trade_date, "indices": [], "breadth": {}, "summary": {}}

    with conn.cursor() as cur:
        # 指數數據（主要指數）
        cur.execute(
            """
            SELECT code, date, open, high, low, close, volume, amount, pctChg
            FROM index_daily
            WHERE date = %s AND frequency = 'day'
            AND code IN ('sh.000001', 'sz.399001', 'sz.399006', 'sh.000300', 'sh.000016', 'sh.000688')
            ORDER BY code
            """,
            (trade_date,),
        )
        for row in cur.fetchall():
            overview["indices"].append({
                "code": row["code"],
                "close": float(row["close"]) if row["close"] else 0,
                "pctChg": float(row["pctChg"]) if row["pctChg"] else 0,
                "amount": float(row["amount"]) if row["amount"] else 0,
            })

        # 市場廣度（漲跌家數）
        cur.execute(
            """
            SELECT
                SUM(CASE WHEN pctChg > 0 THEN 1 ELSE 0 END) AS rising,
                SUM(CASE WHEN pctChg < 0 THEN 1 ELSE 0 END) AS falling,
                SUM(CASE WHEN pctChg = 0 THEN 1 ELSE 0 END) AS flat,
                COUNT(*) AS total,
                SUM(CASE WHEN pctChg >= 9.9 THEN 1 ELSE 0 END) AS limit_up,
                SUM(CASE WHEN pctChg <= -9.9 THEN 1 ELSE 0 END) AS limit_down
            FROM stock_daily
            WHERE date = %s AND adjustflag = 3
            """,
            (trade_date,),
        )
        row = cur.fetchone()
        if row:
            overview["breadth"] = {
                "rising": int(row["rising"] or 0),
                "falling": int(row["falling"] or 0),
                "flat": int(row["flat"] or 0),
                "total": int(row["total"] or 0),
                "limit_up": int(row["limit_up"] or 0),
                "limit_down": int(row["limit_down"] or 0),
            }

        # 匯總
        cur.execute(
            """
            SELECT
                COUNT(DISTINCT code) AS stock_count,
                SUM(amount) AS total_amount,
                AVG(pctChg) AS avg_pct_chg
            FROM stock_daily
            WHERE date = %s AND adjustflag = 3
            """,
            (trade_date,),
        )
        row = cur.fetchone()
        if row:
            overview["summary"] = {
                "stock_count": int(row["stock_count"] or 0),
                "total_amount": float(row["total_amount"] or 0),
                "avg_pct_chg": float(row["avg_pct_chg"] or 0),
            }

    return overview


def _compute_industry_prosperity(conn, trade_date: str) -> list[dict]:
    """計算行業景氣度排名（與 Java IndustryService 邏輯一致）。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT industry, date, avg_pct_chg, total_amount, avg_turn,
                   rising_count, falling_count, stock_count
            FROM industry_daily
            WHERE date = %s
            ORDER BY avg_pct_chg DESC
            """,
            (trade_date,),
        )
        entities = cur.fetchall()

    if not entities:
        return []

    # 提取各維度數據
    pct_chgs = [float(e["avg_pct_chg"] or 0) for e in entities]
    amounts = [float(e["total_amount"] or 0) for e in entities]
    turns = [float(e["avg_turn"] or 0) for e in entities]
    breadths = []
    for e in entities:
        rising = int(e["rising_count"] or 0)
        falling = int(e["falling_count"] or 0)
        total = rising + falling
        breadths.append(rising / total * 100 if total > 0 else 50)

    # 標準化
    def normalize(val, min_val, max_val):
        if max_val == min_val:
            return 50.0
        return (val - min_val) / (max_val - min_val) * 100

    pct_min, pct_max = min(pct_chgs), max(pct_chgs)
    amt_min, amt_max = min(amounts), max(amounts)
    turn_min, turn_max = min(turns), max(turns)
    breadth_min, breadth_max = min(breadths), max(breadths)

    results = []
    for i, e in enumerate(entities):
        momentum = normalize(pct_chgs[i], pct_min, pct_max)
        capital = normalize(amounts[i], amt_min, amt_max)
        activity = normalize(turns[i], turn_min, turn_max)
        breadth = normalize(breadths[i], breadth_min, breadth_max)

        prosperity = momentum * 0.35 + capital * 0.25 + activity * 0.20 + breadth * 0.20

        grade = "優" if prosperity >= 75 else "良" if prosperity >= 50 else "中" if prosperity >= 25 else "差"

        results.append({
            "industry": e["industry"],
            "avg_pct_chg": round(pct_chgs[i], 4),
            "total_amount": round(amounts[i], 2),
            "avg_turn": round(turns[i], 4),
            "rising_count": int(e["rising_count"] or 0),
            "falling_count": int(e["falling_count"] or 0),
            "momentum_score": round(momentum, 2),
            "capital_score": round(capital, 2),
            "activity_score": round(activity, 2),
            "breadth_score": round(breadth, 2),
            "prosperity_index": round(prosperity, 2),
            "grade": grade,
        })

    results.sort(key=lambda x: x["prosperity_index"], reverse=True)
    return results


def _compute_rotation_signals(conn, trade_date: str, lookback_short: int = 5, lookback_long: int = 20) -> list[dict]:
    """計算行業輪動信號（短期 vs 長期動量對比）。"""
    with conn.cursor() as cur:
        # 獲取最近 lookback_long 天的行業數據
        cur.execute(
            """
            SELECT industry, date, avg_pct_chg
            FROM industry_daily
            WHERE date >= DATE_SUB(%s, INTERVAL %s DAY)
            AND date <= %s
            ORDER BY industry, date
            """,
            (trade_date, lookback_long, trade_date),
        )
        rows = cur.fetchall()

    if not rows:
        return []

    # 按行業分組
    industry_data: dict[str, list[float]] = {}
    for row in rows:
        ind = row["industry"]
        if ind not in industry_data:
            industry_data[ind] = []
        industry_data[ind].append(float(row["avg_pct_chg"] or 0))

    signals = []
    for industry, pct_chgs in industry_data.items():
        if len(pct_chgs) < 2:
            continue
        short_avg = sum(pct_chgs[-lookback_short:]) / min(len(pct_chgs[-lookback_short:]), len(pct_chgs))
        long_avg = sum(pct_chgs) / len(pct_chgs)

        # 輪動信號：短期動量 vs 長期動量
        diff = short_avg - long_avg
        if diff > 0.5:
            signal = "加速上漲"
        elif diff > 0:
            signal = "溫和上行"
        elif diff > -0.5:
            signal = "溫和下行"
        else:
            signal = "加速下跌"

        signals.append({
            "industry": industry,
            "short_term_avg": round(short_avg, 4),
            "long_term_avg": round(long_avg, 4),
            "momentum_diff": round(diff, 4),
            "signal": signal,
        })

    signals.sort(key=lambda x: x["momentum_diff"], reverse=True)
    return signals


def _compute_market_breadth_history(conn, trade_date: str, days: int = 10) -> list[dict]:
    """計算最近 N 天的市場廣度歷史。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                date,
                SUM(CASE WHEN pctChg > 0 THEN 1 ELSE 0 END) AS rising,
                SUM(CASE WHEN pctChg < 0 THEN 1 ELSE 0 END) AS falling,
                SUM(CASE WHEN pctChg = 0 THEN 1 ELSE 0 END) AS flat,
                COUNT(*) AS total,
                AVG(pctChg) AS avg_pct_chg,
                SUM(amount) AS total_amount
            FROM stock_daily
            WHERE adjustflag = 3
            AND date >= DATE_SUB(%s, INTERVAL %s DAY)
            AND date <= %s
            GROUP BY date
            ORDER BY date DESC
            """,
            (trade_date, days, trade_date),
        )
        rows = cur.fetchall()

    return [
        {
            "date": str(r["date"]),
            "rising": int(r["rising"] or 0),
            "falling": int(r["falling"] or 0),
            "flat": int(r["flat"] or 0),
            "total": int(r["total"] or 0),
            "avg_pct_chg": round(float(r["avg_pct_chg"] or 0), 4),
            "total_amount": round(float(r["total_amount"] or 0), 2),
        }
        for r in rows
    ]


def _save_snapshot(conn, trade_date: str, snapshot_type: str, data: any) -> None:
    """保存快照到數據庫（UPSERT）。"""
    sql = """
    INSERT INTO market_analysis_snapshot (trade_date, snapshot_type, snapshot_data, computed_at)
    VALUES (%s, %s, %s, NOW())
    ON DUPLICATE KEY UPDATE
        snapshot_data = VALUES(snapshot_data),
        computed_at = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (trade_date, snapshot_type, json.dumps(data, ensure_ascii=False)))
    conn.commit()
    logger.info(f"[預計算] 保存快照: {snapshot_type} for {trade_date}")


def run_precompute(target_date: str | None = None, auto: bool = False) -> int:
    """執行預計算。返回 0=成功，1=失敗。"""
    _load_env(Path(__file__).resolve().parent.parent)

    try:
        conn = _connect()
    except Exception as e:
        logger.error(f"[預計算] MySQL 連接失敗: {e}")
        return 1

    try:
        _ensure_snapshot_table(conn)

        # 確定交易日
        trade_date = target_date or _get_latest_trade_date(conn)
        if not trade_date:
            logger.warning("[預計算] 無可用交易日數據，跳過預計算")
            return 0

        logger.info(f"[預計算] 開始計算 {trade_date} 的行情快照...")

        # 1. 市場概覽
        try:
            overview = _compute_market_overview(conn, trade_date)
            _save_snapshot(conn, trade_date, "market_overview", overview)
            logger.info(f"[預計算] 市場概覽: {len(overview['indices'])} 指數, "
                        f"漲{overview['breadth'].get('rising', 0)}/跌{overview['breadth'].get('falling', 0)}")
        except Exception as e:
            logger.warning(f"[預計算] 市場概覽計算失敗: {e}")

        # 2. 行業景氣度
        try:
            prosperity = _compute_industry_prosperity(conn, trade_date)
            _save_snapshot(conn, trade_date, "industry_prosperity", prosperity)
            logger.info(f"[預計算] 行業景氣度: {len(prosperity)} 個行業")
        except Exception as e:
            logger.warning(f"[預計算] 行業景氣度計算失敗: {e}")

        # 3. 輪動信號
        try:
            rotation = _compute_rotation_signals(conn, trade_date)
            _save_snapshot(conn, trade_date, "rotation_signals", rotation)
            logger.info(f"[預計算] 輪動信號: {len(rotation)} 個行業")
        except Exception as e:
            logger.warning(f"[預計算] 輪動信號計算失敗: {e}")

        # 4. 市場廣度歷史
        try:
            breadth_history = _compute_market_breadth_history(conn, trade_date, days=10)
            _save_snapshot(conn, trade_date, "market_breadth", breadth_history)
            logger.info(f"[預計算] 市場廣度: {len(breadth_history)} 天歷史")
        except Exception as e:
            logger.warning(f"[預計算] 市場廣度計算失敗: {e}")

        logger.info(f"[預計算] 完成！{trade_date} 的行情快照已保存")
        return 0

    except Exception as e:
        logger.error(f"[預計算] 失敗: {e}", exc_info=True)
        return 1
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="行情預計算快照")
    parser.add_argument("--date", default="", help="目標交易日 YYYY-MM-DD（默認最新交易日）")
    parser.add_argument("--auto", action="store_true", help="自動模式（由 ingestion 調用，失敗不阻塞）")
    args = parser.parse_args()

    return run_precompute(target_date=args.date or None, auto=args.auto)


if __name__ == "__main__":
    sys.exit(main())
