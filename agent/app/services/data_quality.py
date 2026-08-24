"""數據質量檢查服務 — 純 SQL 規則集，定時執行，結果落庫 + 可選 AI 總結。

設計原則：
- 檢測層 100% 用 SQL 規則（零幻覺、可重現、可做 CI 閘門）
- AI 僅做總結報告生成（總結，不檢測）
- 結果寫入 data_quality_report 表（Java 後端 schema 管理）

規則覆蓋：
1. 日期缺口（股票/指數缺失交易日）
2. 重複行（唯一鍵衝突）
3. 非法值（價格≤0、成交量<0）
4. 前復權陳舊化（adjustflag=2 最新日期 vs adjustflag=3）
5. 行業分類缺失
6. 新聞 URI 重複
7. 表行數統計（異常下降告警）
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, date
from typing import Any

import pymysql

logger = logging.getLogger("agent.data_quality")

# ===== SQL 規則集 =====
# 每條規則: (rule_id, severity, description, sql, expected_zero_results)
# expected_zero_results=True 表示期望結果為空（有結果=有問題）
QUALITY_RULES: list[tuple[str, str, str, str, bool]] = [
    # === 1. 重複行檢測 ===
    (
        "dup_stock_daily",
        "CRITICAL",
        "stock_daily 重複行（唯一鍵 code+date+adjustflag 應唯一）",
        """
        SELECT code, date, adjustflag, COUNT(*) as cnt
        FROM stock_daily
        GROUP BY code, date, adjustflag
        HAVING cnt > 1
        LIMIT 50
        """,
        True,
    ),
    (
        "dup_index_daily",
        "CRITICAL",
        "index_daily 重複行（唯一鍵 code+date+frequency 應唯一）",
        """
        SELECT code, date, frequency, COUNT(*) as cnt
        FROM index_daily
        GROUP BY code, date, frequency
        HAVING cnt > 1
        LIMIT 50
        """,
        True,
    ),
    (
        "dup_financial_news",
        "WARNING",
        "financial_news URI 重複",
        """
        SELECT uri, COUNT(*) as cnt
        FROM financial_news
        GROUP BY uri
        HAVING cnt > 1
        LIMIT 50
        """,
        True,
    ),
    # === 2. 非法值檢測 ===
    (
        "invalid_price_stock",
        "CRITICAL",
        "stock_daily 價格≤0 或成交量<0",
        """
        SELECT code, date, adjustflag, open, high, low, close, volume
        FROM stock_daily
        WHERE close <= 0 OR open <= 0 OR high <= 0 OR low <= 0 OR volume < 0
        LIMIT 50
        """,
        True,
    ),
    (
        "invalid_price_index",
        "CRITICAL",
        "index_daily 價格≤0",
        """
        SELECT code, date, open, high, low, close
        FROM index_daily
        WHERE close <= 0 OR open <= 0 OR high <= 0 OR low <= 0
        LIMIT 50
        """,
        True,
    ),
    # === 3. 前復權陳舊化（簡化為兩個獨立標量查詢，避免子查詢超時）===
    # 注意：此規則在 run_quality_checks 中特殊處理（兩步查詢）
    (
        "stale_adjustflag2",
        "WARNING",
        "前復權(adjustflag=2)數據陳舊（比不復權(3)最新日期落後超過 7 天）",
        "SELECT MAX(date) AS latest FROM stock_daily WHERE adjustflag = 2",
        True,
    ),
    # === 4. 行業分類缺失 ===
    (
        "missing_industry",
        "WARNING",
        "stock_listing 中有股票但 stock_industry 缺少行業分類",
        """
        SELECT sl.code, sl.code_name
        FROM stock_listing sl
        LEFT JOIN stock_industry si ON sl.code = si.code
        WHERE si.code IS NULL
        LIMIT 100
        """,
        True,
    ),
    # === 5. 日期缺口（僅檢查最新 30 天，避免全表掃描）===
    (
        "missing_dates_latest_stock",
        "WARNING",
        "最近 30 天內有交易日期口（stock_daily adjustflag=3）",
        """
        SELECT
            d.trade_date,
            COUNT(DISTINCT s.code) AS stocks_with_data
        FROM (
            SELECT DISTINCT date AS trade_date
            FROM stock_daily
            WHERE adjustflag = 3 AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        ) d
        LEFT JOIN stock_daily s
            ON s.date = d.trade_date AND s.adjustflag = 3
        GROUP BY d.trade_date
        HAVING stocks_with_data < 100
        ORDER BY d.trade_date DESC
        LIMIT 10
        """,
        True,
    ),
    # === 6. 表行數統計 ===
    (
        "table_row_counts",
        "INFO",
        "各表行數統計（用於監控數據量異常下降）",
        """
        SELECT 'stock_daily' AS tbl, COUNT(*) AS cnt FROM stock_daily
        UNION ALL SELECT 'index_daily', COUNT(*) FROM index_daily
        UNION ALL SELECT 'stock_industry', COUNT(*) FROM stock_industry
        UNION ALL SELECT 'industry_daily', COUNT(*) FROM industry_daily
        UNION ALL SELECT 'financial_news', COUNT(*) FROM financial_news
        UNION ALL SELECT 'backtest_strategy', COUNT(*) FROM backtest_strategy
        UNION ALL SELECT 'ai_call_log', COUNT(*) FROM ai_call_log
        """,
        False,
    ),
    # === 7. 數據範圍 ===
    (
        "data_range",
        "INFO",
        "stock_daily 數據時間範圍",
        """
        SELECT
            MIN(date) AS earliest,
            MAX(date) AS latest,
            COUNT(DISTINCT code) AS distinct_codes,
            COUNT(DISTINCT adjustflag) AS adjustflags
        FROM stock_daily
        """,
        False,
    ),
]


def _get_connection() -> pymysql.Connection:
    """從環境變量構建 MySQL 連接。"""
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


def run_quality_checks() -> dict[str, Any]:
    """執行全部數據質量規則，返回結構化報告。

    每條規則使用獨立連接，避免一條規則超時影響後續規則。

    Returns:
        {
            "check_time": "2026-08-25T10:00:00",
            "total_rules": 10,
            "passed": 7,
            "failed": 3,
            "results": [...]
        }
    """
    check_time = datetime.now().isoformat()
    results = []

    for rule_id, severity, description, sql, expected_zero in QUALITY_RULES:
        try:
            # 每條規則獨立連接，避免超時斷連影響後續規則
            conn = _get_connection()
            try:
                # stale_adjustflag2 特殊處理：利用 idx_date 索引反向掃描（避免全表掃描）
                if rule_id == "stale_adjustflag2":
                    try:
                        with conn.cursor() as cur:
                            # 利用 idx_date 索引反向掃描，找到最新的 adjustflag=3 和 adjustflag=2 的日期
                            cur.execute(
                                "SELECT date FROM stock_daily WHERE adjustflag = 3 "
                                "ORDER BY date DESC LIMIT 1"
                            )
                            row = cur.fetchone()
                            latest_raw = row["date"] if row else None
                            cur.execute(
                                "SELECT date FROM stock_daily WHERE adjustflag = 2 "
                                "ORDER BY date DESC LIMIT 1"
                            )
                            row = cur.fetchone()
                            latest_adj2 = row["date"] if row else None

                        if latest_raw and latest_adj2:
                            from datetime import datetime as _dt
                            if isinstance(latest_raw, str):
                                latest_raw = _dt.strptime(latest_raw, "%Y-%m-%d").date()
                            if isinstance(latest_adj2, str):
                                latest_adj2 = _dt.strptime(latest_adj2, "%Y-%m-%d").date()
                            gap = (latest_raw - latest_adj2).days
                            passed = gap <= 7
                            row_count = 0 if passed else 1
                            results.append({
                                "rule_id": rule_id,
                                "severity": severity,
                                "description": description,
                                "row_count": row_count,
                                "passed": passed,
                                "sample_rows": [{"latest_raw": str(latest_raw), "latest_adj2": str(latest_adj2), "gap_days": gap}],
                            })
                            logger.info(f"[數據質量] {'PASS' if passed else 'FAIL'} {rule_id}: gap={gap}d")
                        else:
                            results.append({
                                "rule_id": rule_id,
                                "severity": severity,
                                "description": description,
                                "row_count": 0,
                                "passed": True,
                                "sample_rows": [],
                            })
                            logger.info(f"[數據質量] PASS {rule_id}: 無數據可比")
                    except Exception as e:
                        results.append({
                            "rule_id": rule_id,
                            "severity": severity,
                            "description": description,
                            "row_count": -1,
                            "passed": False,
                            "error": str(e),
                            "sample_rows": [],
                        })
                        logger.warning(f"[數據質量] 規則 {rule_id} 執行失敗: {e}")
                    continue

                with conn.cursor() as cur:
                    cur.execute(sql)
                    rows = cur.fetchall()
                    row_count = len(rows)

                    if expected_zero:
                        passed = row_count == 0
                    else:
                        passed = True  # INFO 級別不判 pass/fail

                    results.append({
                        "rule_id": rule_id,
                        "severity": severity,
                        "description": description,
                        "row_count": row_count,
                        "passed": passed,
                        "sample_rows": rows[:5] if rows else [],
                    })

                    status = "PASS" if passed else "FAIL"
                    logger.info(
                        f"[數據質量] {status} {rule_id} ({severity}): "
                        f"{row_count} 行問題數據"
                    )
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"[數據質量] 規則 {rule_id} 執行失敗: {e}")
            results.append({
                "rule_id": rule_id,
                "severity": severity,
                "description": description,
                "row_count": -1,
                "passed": False,
                "error": str(e),
                "sample_rows": [],
            })

    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count

    report = {
        "check_time": check_time,
        "total_rules": len(QUALITY_RULES),
        "passed": passed_count,
        "failed": failed_count,
        "results": results,
    }

    logger.info(
        f"[數據質量] 檢查完成: {passed_count}/{len(results)} 通過, "
        f"{failed_count} 失敗"
    )

    return report


def format_report_for_ai(report: dict[str, Any]) -> str:
    """將質量報告格式化為 LLM 可讀的文本（用於 AI 週報生成）。"""
    lines = [
        f"# 數據質量檢查報告（{report['check_time'][:19]}）",
        f"",
        f"總規則數: {report['total_rules']}, 通過: {report['passed']}, 失敗: {report['failed']}",
        f"",
    ]

    for r in report["results"]:
        status = "✅" if r["passed"] else "❌"
        lines.append(f"## {status} {r['rule_id']} ({r['severity']})")
        lines.append(f"描述: {r['description']}")
        lines.append(f"問題行數: {r['row_count']}")
        if r.get("error"):
            lines.append(f"執行錯誤: {r['error']}")
        if r.get("sample_rows"):
            lines.append("樣本（前 5 行）:")
            for row in r["sample_rows"][:3]:
                lines.append(f"  {row}")
        lines.append("")

    return "\n".join(lines)


async def generate_ai_summary(report: dict[str, Any]) -> str | None:
    """用免費 LLM（glm-flash）生成數據質量報告的自然語言總結。

    這是 AI 的正確用法：總結，不檢測。SQL 規則做檢測，AI 做解讀。
    """
    try:
        from app.core.llm_client import llm_client

        report_text = format_report_for_ai(report)

        prompt = f"""你是數據質量分析師。請根據以下 SQL 規則檢查結果，生成一份簡潔的中文質量報告。

要求：
1. 總體評分（優/良/差）+ 理由
2. 列出所有失敗的 CRITICAL 規則，說明影響
3. 列出 WARNING 規則，給出修復建議
4. 結尾給出「下一步行動」清單（最多 3 條）

{report_text}"""

        result = await llm_client.analyze(
            prompt,
            provider="glm-flash",
            system="你是數據質量分析師，擅長從 SQL 檢查結果中發現數據問題並給出修復建議。",
        )

        if result and result.get("text"):
            return result["text"]
        return None
    except Exception as e:
        logger.warning(f"AI 總結生成失敗: {e}")
        return None
