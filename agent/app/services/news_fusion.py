"""雙路召回融合 — RRF (Reciprocal Rank Fusion) 評分。

將向量檢索（語義相似）和 BM25 檢索（關鍵詞匹配）的結果融合排序。

RRF 公式：
    score(d) = Σ 1 / (k + rank_i(d))
    其中 k 是平滑常數（通常 60），rank_i(d) 是文檔 d 在第 i 路檢索中的排名

優勢：
- 無需歸一化不同檢索器的分數（向量 COSINE vs BM25 分數尺度不同）
- 對排名敏感而非分數敏感，魯棒性強
- 簡單高效，無需訓練

額外評分加權：
- 向量檢索結果帶 similarity 分數 → 可作為加權因子
- BM25 結果帶 bm25_score → 可作為加權因子
- 時間新鮮度加權：越新的新聞加分越多
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("agent.news_fusion")

# RRF 平滑常數（標準值 60）
_RRF_K = 60

# 時間新鮮度加權：最近 N 天的新聞加分
_FRESHNESS_DAYS = 3
_FRESHNESS_BONUS = 0.1  # 最近 3 天的新聞額外加 0.1 分


def reciprocal_rank_fusion(
    vector_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """RRF 融合向量檢索和 BM25 檢索結果。

    Args:
        vector_results: 向量檢索結果（每項含 uri, similarity, ...）
        bm25_results: BM25 檢索結果（每項含 uri, bm25_score, ...）
        top_k: 返回條數

    Returns:
        融合排序後的新聞列表，每項含：
        - uri, title, summary, source, channel, date, url
        - rrf_score: 融合評分
        - vector_rank: 向量檢索排名（從 1 開始，0 表示未出現）
        - bm25_rank: BM25 檢索排名（從 1 開始，0 表示未出現）
        - similarity: 向量相似度（若有）
        - bm25_score: BM25 分數（若有）
    """
    # 以 URI 為 key 合併兩路結果
    merged: dict[str, dict[str, Any]] = {}

    # 向量檢索結果排名（從 1 開始）
    for rank, item in enumerate(vector_results, start=1):
        uri = item.get("uri", "")
        if not uri:
            continue
        if uri not in merged:
            merged[uri] = {
                "uri": uri,
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", "華爾街見聞"),
                "channel": item.get("channel", ""),
                "date": item.get("date", ""),
                "url": item.get("url", ""),
                "vector_rank": rank,
                "bm25_rank": 0,
                "similarity": item.get("similarity", 0.0),
                "bm25_score": 0.0,
            }
        else:
            merged[uri]["vector_rank"] = rank
            merged[uri]["similarity"] = item.get("similarity", 0.0)

    # BM25 檢索結果排名
    for rank, item in enumerate(bm25_results, start=1):
        uri = item.get("uri", "")
        if not uri:
            continue
        if uri not in merged:
            merged[uri] = {
                "uri": uri,
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", "華爾街見聞"),
                "channel": item.get("channel", ""),
                "date": item.get("date", ""),
                "url": item.get("url", ""),
                "vector_rank": 0,
                "bm25_rank": rank,
                "similarity": 0.0,
                "bm25_score": item.get("bm25_score", 0.0),
            }
        else:
            merged[uri]["bm25_rank"] = rank
            merged[uri]["bm25_score"] = item.get("bm25_score", 0.0)

    # 計算 RRF 分數
    now = datetime.now(tz=timezone.utc)
    for uri, item in merged.items():
        rrf = 0.0
        if item["vector_rank"] > 0:
            rrf += 1.0 / (_RRF_K + item["vector_rank"])
        if item["bm25_rank"] > 0:
            rrf += 1.0 / (_RRF_K + item["bm25_rank"])

        # 時間新鮮度加權
        date_str = item.get("date", "")
        if date_str:
            try:
                doc_date = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                age_days = (now - doc_date).days
                if age_days <= _FRESHNESS_DAYS:
                    rrf += _FRESHNESS_BONUS
            except (ValueError, OSError):
                pass

        item["rrf_score"] = round(rrf, 6)

    # 按 RRF 分數排序
    ranked = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)

    # 取 top_k
    result = ranked[:top_k]

    # 日誌：兩路都命中的結果（最優質）
    both_hit = sum(1 for r in result if r["vector_rank"] > 0 and r["bm25_rank"] > 0)
    vector_only = sum(1 for r in result if r["vector_rank"] > 0 and r["bm25_rank"] == 0)
    bm25_only = sum(1 for r in result if r["vector_rank"] == 0 and r["bm25_rank"] > 0)
    logger.info(
        f"[news_fusion] RRF 融合: {len(result)} 條"
        f"（兩路命中={both_hit}, 僅向量={vector_only}, 僅BM25={bm25_only}）"
    )

    return result
