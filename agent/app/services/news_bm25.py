"""BM25 關鍵詞檢索 — 與向量檢索互補的雙路召回。

設計：
- 從 Milvus 拉取所有新聞的 title + summary，構建內存 BM25 索引
- 使用 jieba 中文分詞
- 查詢時返回 BM25 排序結果（與向量檢索結果做 RRF 融合）
- 索引懶加載 + 定期刷新（避免每次查詢都重建）

BM25 vs 向量檢索的互補性：
- 向量檢索：語義相似（「半導體」能匹配「芯片」），但可能漏掉精確關鍵詞
- BM25：精確關鍵詞匹配（「央行降準」能精確命中），但不懂語義
- 融合後：既覆蓋語義相似又覆蓋精確匹配，召回率顯著提升
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("agent.news_bm25")

# 延遲導入 — jieba 和 rank_bm25 是可選依賴
_jieba = None
_BM25Okapi = None
_init_attempted = False
_init_error = ""

# BM25 索引緩存
_bm25_index = None  # BM25Okapi 實例
_bm25_documents: list[dict[str, Any]] = []  # 對應的新聞文檔列表
_bm25_tokenized: list[list[str]] = []  # 分詞後的文檔列表
_index_last_build_time: float = 0.0
_INDEX_REFRESH_INTERVAL = 300  # 索引刷新間隔（秒），5 分鐘


def _try_init():
    """延遲初始化 jieba 和 rank_bm25。"""
    global _jieba, _BM25Okapi, _init_attempted, _init_error
    if _init_attempted:
        return
    _init_attempted = True
    try:
        import jieba

        _jieba = jieba
        # 設置 jieba 日誌級別（避免刷屏）
        jieba.setLogLevel(logging.WARNING)
        logger.info("[news_bm25] jieba 分詞器載入成功")
    except ImportError as e:
        _init_error = f"jieba 未安裝: {e}"
        logger.warning(_init_error)
        return

    try:
        from rank_bm25 import BM25Okapi

        _BM25Okapi = BM25Okapi
        logger.info("[news_bm25] rank_bm25 載入成功")
    except ImportError as e:
        _init_error = f"rank_bm25 未安裝: {e}"
        logger.warning(_init_error)


def _tokenize(text: str) -> list[str]:
    """使用 jieba 分詞，過濾停用詞和空白。"""
    if not _jieba or not text:
        return []
    # 精確模式分詞
    words = _jieba.lcut(text)
    # 過濾：去除單字符、純數字、純標點、空白
    return [w.strip() for w in words if len(w.strip()) >= 2 and not w.strip().isdigit()]


def _build_index(documents: list[dict[str, Any]]) -> bool:
    """從新聞文檔列表構建 BM25 索引。

    Args:
        documents: 新聞列表（每條含 title, summary）

    Returns:
        bool: 是否成功構建
    """
    global _bm25_index, _bm25_documents, _bm25_tokenized, _index_last_build_time
    _try_init()
    if not _BM25Okapi or not _jieba:
        return False

    if not documents:
        _bm25_index = None
        _bm25_documents = []
        _bm25_tokenized = []
        return False

    # 分詞所有文檔
    _bm25_documents = documents
    _bm25_tokenized = []
    for doc in documents:
        title = doc.get("title", "") or ""
        summary = doc.get("summary", "") or ""
        text = f"{title} {summary}"
        _bm25_tokenized.append(_tokenize(text))

    try:
        _bm25_index = _BM25Okapi(_bm25_tokenized)
        _index_last_build_time = time.time()
        logger.info(f"[news_bm25] 索引構建完成: {len(documents)} 篇文檔")
        return True
    except Exception as e:
        logger.warning(f"[news_bm25] 索引構建失敗: {e}")
        _bm25_index = None
        return False


def _ensure_index(documents: list[dict[str, Any]] | None = None) -> bool:
    """確保 BM25 索引可用（懶加載 + 定期刷新）。

    Args:
        documents: 可選的新聞文檔列表（若提供則用於構建/刷新索引）
                   若不提供則嘗試從 Milvus 拉取
    """
    global _index_last_build_time

    now = time.time()
    # 索引仍新鮮 → 直接用
    if _bm25_index is not None and (now - _index_last_build_time) < _INDEX_REFRESH_INTERVAL:
        return True

    # 索引過期或不存在 → 需要重建
    if documents is not None:
        return _build_index(documents)

    # 沒有文檔數據 → 嘗試從 Milvus 拉取
    if _bm25_index is None:
        docs = _fetch_documents_from_milvus()
        if docs:
            return _build_index(docs)
        return False

    # 索引過期但無新數據 → 用舊索引（總比沒有好）
    return True


def _fetch_documents_from_milvus() -> list[dict[str, Any]]:
    """從 Milvus 拉取所有新聞文檔（用於構建 BM25 索引）。"""
    try:
        from app.services.news_store import _milvus, _ensure_collection, COLLECTION_NAME

        if not _milvus or not _ensure_collection():
            return []
        results = _milvus.query(
            collection_name=COLLECTION_NAME,
            filter="timestamp > 0",
            output_fields=["uri", "title", "summary", "source", "channel", "date", "url"],
            limit=10000,
        )
        logger.info(f"[news_bm25] 從 Milvus 拉取 {len(results)} 篇文檔")
        return results
    except Exception as e:
        logger.warning(f"[news_bm25] 從 Milvus 拉取文檔失敗: {e}")
        return []


def search_bm25(
    query: str,
    top_k: int = 10,
    documents: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """BM25 關鍵詞檢索。

    Args:
        query: 查詢文本
        top_k: 返回條數
        documents: 可選的文檔列表（若提供則用於構建/刷新索引）

    Returns:
        新聞列表，每項含 title/summary/source/date/url/channel/bm25_score
    """
    _try_init()
    if not _BM25Okapi or not _jieba:
        return []

    if not _ensure_index(documents):
        return []

    if not query or not _bm25_index:
        return []

    # 分詞查詢
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    try:
        # BM25 打分
        scores = _bm25_index.get_scores(query_tokens)

        # 取 top_k 結果
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for idx in ranked_indices[:top_k]:
            score = float(scores[idx])
            # 檢查文檔是否包含任一查詢詞（BM25 在小語料庫可能返回負分，
            # 但只要文檔包含查詢詞就視為相關）
            doc_tokens = _bm25_tokenized[idx] if idx < len(_bm25_tokenized) else []
            has_match = any(qt in doc_tokens for qt in query_tokens)
            if not has_match:
                continue
            doc = _bm25_documents[idx]
            results.append({
                "uri": doc.get("uri", ""),
                "title": doc.get("title", ""),
                "summary": doc.get("summary", ""),
                "source": doc.get("source", "華爾街見聞"),
                "channel": doc.get("channel", ""),
                "date": doc.get("date", ""),
                "url": doc.get("url", ""),
                "bm25_score": round(score, 4),
            })
        logger.info(f"[news_bm25] BM25 檢索「{query[:30]}...」: {len(results)} 條")
        return results
    except Exception as e:
        logger.warning(f"[news_bm25] BM25 檢索失敗: {e}")
        return []


def is_available() -> bool:
    """BM25 檢索是否可用。"""
    _try_init()
    return _BM25Okapi is not None and _jieba is not None


def get_status() -> dict[str, Any]:
    """獲取 BM25 索引狀態。"""
    return {
        "available": is_available(),
        "index_size": len(_bm25_documents),
        "index_age_seconds": round(time.time() - _index_last_build_time, 1) if _index_last_build_time > 0 else 0,
        "refresh_interval_seconds": _INDEX_REFRESH_INTERVAL,
        "init_error": _init_error,
    }


def rebuild_index(documents: list[dict[str, Any]] | None = None) -> bool:
    """強制重建 BM25 索引。

    Args:
        documents: 可選的文檔列表（若不提供則從 Milvus 拉取）

    Returns:
        bool: 是否成功重建
    """
    global _index_last_build_time
    _index_last_build_time = 0  # 強制過期
    if documents is not None:
        return _build_index(documents)
    docs = _fetch_documents_from_milvus()
    if docs:
        return _build_index(docs)
    return False
