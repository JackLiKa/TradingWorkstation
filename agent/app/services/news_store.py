"""財經新聞存儲/檢索服務 — MySQL + Milvus 向量庫雙寫。

職責：
- 抓取華爾街見聞新聞 → 清洗 → 寫入 MySQL（financial_news 表）
- 同時向量化 → 寫入 Milvus（financial_news_vectors collection）
- AI0 行情新聞階段調用：語義檢索與當前市場相關的新聞
- 關鍵詞搜索：按行業/關鍵詞檢索相關新聞

向量庫分片規則（按文章分片，提高命中率減少幻覺）：
- 每篇文章 = 1 個向量（embed = 標題 + 摘要 + 關鍵實體）
- metadata: 日期/來源/頻道/URL/URI
- HNSW 索引 + COSINE 距離
- 30 天 TTL（自動清理過期新聞）
- URI 去重（避免重複入庫）

設計要點：
- 自動降級：Milvus/MySQL 不可用時靜默跳過，不影響優化循環
- 與 vector_store.py 共享 embedding 模型（避免重複載入）
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.services import wallstreetcn_client

logger = logging.getLogger("agent.news_store")

# ===== 配置 =====
_NEWS_TTL_DAYS = int(os.environ.get("NEWS_TTL_DAYS", "30"))  # 新聞保留天數
_MAX_NEWS_VECTORS = int(os.environ.get("NEWS_MAX_VECTORS", "10000"))  # 最多保留向量數

# 延遲導入 — Milvus 和 sentence-transformers 是可選依賴（與 vector_store.py 共享）
_milvus = None
_embedding_model = None
_init_attempted = False
_init_error = ""
_init_fail_count = 0
_MAX_INIT_RETRIES = 3

COLLECTION_NAME = "financial_news_vectors"
EMBEDDING_DIM = 512  # bge-small-zh-v1.5 輸出維度（與 vector_store.py 一致）


def _try_init():
    """延遲初始化 Milvus 和 embedding 模型（與 vector_store.py 共享實例）。

    優先復用 vector_store 已初始化的模型，避免重複載入。
    """
    global _milvus, _embedding_model, _init_attempted, _init_error, _init_fail_count
    if _init_attempted and _init_fail_count >= _MAX_INIT_RETRIES:
        return
    if _init_attempted and _milvus is not None and _embedding_model is not None:
        return
    _init_attempted = True

    # 優先復用 vector_store 的實例
    try:
        from app.services import vector_store

        if vector_store._milvus is not None:
            _milvus = vector_store._milvus
            logger.info("[news_store] 復用 vector_store 的 Milvus 實例")
        if vector_store._embedding_model is not None:
            _embedding_model = vector_store._embedding_model
            logger.info("[news_store] 復用 vector_store 的 embedding 模型")
        if _milvus is not None and _embedding_model is not None:
            return
    except Exception:
        pass

    # 若 vector_store 未初始化，自行初始化
    if _milvus is None:
        try:
            from pymilvus import MilvusClient

            data_dir = Path(__file__).resolve().parent.parent.parent / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "milvus_lite.db")
            _milvus = MilvusClient(db_path)
            logger.info(f"[news_store] Milvus Lite 初始化成功: {db_path}")
        except Exception as e:
            _init_fail_count += 1
            _init_error = f"Milvus 初始化失敗 (第{_init_fail_count}次): {e}"
            logger.warning(_init_error)
            return

    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            model_name = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
            _embedding_model = SentenceTransformer(model_name)
            logger.info(f"[news_store] Embedding 模型載入成功: {model_name}")
            _init_fail_count = 0
        except Exception as e:
            _init_fail_count += 1
            _init_error = f"Embedding 模型載入失敗 (第{_init_fail_count}次): {e}"
            logger.warning(_init_error)
            _milvus = None


def _ensure_collection():
    """確保 financial_news_vectors collection 存在並已載入記憶體。"""
    if not _milvus:
        return False
    try:
        from pymilvus import DataType

        if _milvus.has_collection(COLLECTION_NAME):
            # 確保 collection 已載入（Milvus Lite 重啟後狀態為 released）
            try:
                _milvus.load_collection(COLLECTION_NAME)
            except Exception:
                pass  # 已載入或載入中，忽略
            return True

        schema = _milvus.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
        schema.add_field("uri", DataType.VARCHAR, max_length=200)  # 文章唯一標識（去重）
        schema.add_field("title", DataType.VARCHAR, max_length=500)
        schema.add_field("summary", DataType.VARCHAR, max_length=1000)
        schema.add_field("source", DataType.VARCHAR, max_length=50)
        schema.add_field("channel", DataType.VARCHAR, max_length=50)
        schema.add_field("date", DataType.VARCHAR, max_length=20)  # YYYY-MM-DD
        schema.add_field("url", DataType.VARCHAR, max_length=500)
        schema.add_field("timestamp", DataType.INT64)  # 時間戳（用於 TTL 清理）

        index_params = _milvus.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )
        _milvus.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )
        _milvus.load_collection(COLLECTION_NAME)
        logger.info(f"[news_store] Milvus collection 創建並載入: {COLLECTION_NAME}")
        return True
    except Exception as e:
        logger.warning(f"[news_store] Milvus collection 創建失敗: {e}")
        return False


def _embed_news(
    title: str,
    summary: str,
    channel: str = "",
    article: dict[str, Any] | None = None,
) -> list[float] | None:
    """將新聞向量化 — embed = 標題 + 摘要 + 正文前200字 + 頻道（語義豐富）。

    分片規則：每篇文章 = 1 個向量
    - embed 文本 = "標題。摘要。正文前200字。頻道: {channel}"
    - 豐富的語義文本提升檢索命中率，減少幻覺
    - 頻道信息幫助區分 A 股/美股/商品等不同市場的新聞
    """
    if not _embedding_model:
        return None
    try:
        # 構建語義豐富的 embed 文本（標題 + 摘要 + 正文前200字 + 頻道）
        parts = [title]
        if summary:
            parts.append(summary)
        # 加入正文前200字增加語義信息
        content = article.get("content", "") if isinstance(article, dict) else ""
        if content and len(content) > len(summary or ""):
            parts.append(content[:200])
        text = "。".join(parts)
        if channel:
            text += f"。頻道: {channel}"
        vec = _embedding_model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        logger.warning(f"[news_store] 新聞 embedding 失敗: {e}")
        return None


def _compute_uri_hash(uri: str) -> str:
    """計算 URI 的哈希（用於精確去重）。"""
    return hashlib.sha256(uri.encode("utf-8")).hexdigest()[:16]


# 內存級 URI 去重快取（避免頻繁查詢 Milvus + 防止 collection released 時誤判）
_uri_cache: set[str] = set()
_uri_cache_loaded = False


def _load_uri_cache():
    """從 Milvus 載入所有已存在的 URI 到內存快取。"""
    global _uri_cache_loaded
    if _uri_cache_loaded or not _milvus or not _ensure_collection():
        return
    try:
        results = _milvus.query(
            collection_name=COLLECTION_NAME,
            filter="timestamp > 0",  # 匹配所有記錄
            output_fields=["uri"],
            limit=10000,
        )
        _uri_cache.update(item.get("uri", "") for item in results if item.get("uri"))
        _uri_cache_loaded = True
        logger.info(f"[news_store] URI 快取載入: {len(_uri_cache)} 條")
    except Exception as e:
        logger.warning(f"[news_store] URI 快取載入失敗: {e}")


def _uri_exists(uri: str) -> bool:
    """檢查 URI 是否已存在（內存快取優先，Milvus 查詢兜底）。

    異常時保守返回 True（假定已存在，跳過插入，避免重複）。
    """
    # 1. 內存快取快速判斷
    if uri in _uri_cache:
        return True
    # 2. Milvus 查詢兜底（快取未命中時）
    if not _milvus or not _ensure_collection():
        return True  # 無法確認，保守跳過
    try:
        safe_uri = uri.replace("'", "\\'")
        results = _milvus.query(
            collection_name=COLLECTION_NAME,
            filter=f"uri == '{safe_uri}'",
            output_fields=["uri"],
            limit=1,
        )
        if len(results) > 0:
            _uri_cache.add(uri)  # 加入快取
            return True
        return False
    except Exception as e:
        logger.warning(f"[news_store] URI 去重檢查失敗（保守跳過）: {e}")
        return True  # 異常時保守跳過，避免重複


def store_news(article: dict[str, Any]) -> bool:
    """存儲單篇新聞到向量庫。

    Args:
        article: 標準化新聞 dict（來自 wallstreetcn_client）

    Returns:
        bool: 是否成功存入（已存在返回 False）
    """
    _try_init()
    if not _milvus or not _embedding_model:
        return False
    if not _ensure_collection():
        return False

    # 載入 URI 快取（首次調用時）
    _load_uri_cache()

    uri = article.get("uri", "")
    if not uri:
        return False

    # URI 去重
    if _uri_exists(uri):
        return False

    title = article.get("title", "")
    summary = article.get("summary", "")
    channel = article.get("channel", "")
    date_str = article.get("date", "")
    url = article.get("url", "")
    source = article.get("source", "華爾街見聞")

    # 向量化（傳入完整 article 以獲取 content 字段）
    embedding = _embed_news(title, summary, channel, article)
    if embedding is None:
        return False

    # 解析時間戳（用於 TTL 清理）
    try:
        if date_str:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
        else:
            ts = int(time.time())
    except (ValueError, OSError):
        ts = int(time.time())

    try:
        _milvus.insert(
            collection_name=COLLECTION_NAME,
            data=[
                {
                    "embedding": embedding,
                    "uri": uri[:200],
                    "title": title[:500],
                    "summary": summary[:1000],
                    "source": source[:50],
                    "channel": channel[:50],
                    "date": date_str[:20],
                    "url": url[:500],
                    "timestamp": ts,
                }
            ],
        )
        _uri_cache.add(uri)  # 加入內存快取
        return True
    except Exception as e:
        logger.warning(f"[news_store] 新聞存入向量庫失敗: {e}")
        return False


def store_news_batch(articles: list[dict[str, Any]]) -> dict[str, int]:
    """批量存儲新聞到向量庫。

    Returns:
        dict: {"stored": N, "duplicated": N, "failed": N}
    """
    stored = 0
    duplicated = 0
    failed = 0
    for article in articles:
        uri = article.get("uri", "")
        if not uri:
            failed += 1
            continue
        if _uri_exists(uri):
            duplicated += 1
            continue
        if store_news(article):
            stored += 1
        else:
            failed += 1
    logger.info(
        f"[news_store] 批量存儲: {stored} 新存入, {duplicated} 重複跳過, {failed} 失敗"
    )
    return {"stored": stored, "duplicated": duplicated, "failed": failed}


def search_relevant_news(
    query: str,
    top_k: int = 10,
    channel: str | None = None,
    days_back: int = 7,
) -> list[dict[str, Any]]:
    """語義檢索與查詢相關的新聞。

    用於 AI0 行情新聞階段：傳入當前市場環境描述，檢索相關新聞。

    Args:
        query: 查詢文本（如「半導體行業利好，A股市場震盪」）
        top_k: 返回條數
        channel: 可選頻道過濾（如 "a-stock"）
        days_back: 只檢索最近 N 天的新聞

    Returns:
        新聞列表，每項含 title/summary/source/date/url/channel/similarity
    """
    _try_init()
    if not _milvus or not _embedding_model:
        return []
    if not _ensure_collection():
        return []

    # 向量化查詢（自動豐富短查詢，提升語義匹配率）
    enriched_query = query
    if len(query) < 20:
        # 短查詢自動補充上下文，提升語義匹配
        enriched_query = f"{query} 財經新聞 A股市場 行業動態"
    try:
        query_vec = _embedding_model.encode(enriched_query, normalize_embeddings=True).tolist()
    except Exception as e:
        logger.warning(f"[news_store] 查詢 embedding 失敗: {e}")
        return []

    # 計算時間過濾閾值
    cutoff_ts = int((datetime.now(tz=timezone.utc) - timedelta(days=days_back)).timestamp())

    # 構建過濾條件
    filter_expr = f"timestamp >= {cutoff_ts}"
    if channel:
        filter_expr += f' and channel == "{channel}"'

    try:
        results = _milvus.search(
            collection_name=COLLECTION_NAME,
            data=[query_vec],
            limit=top_k,
            filter=filter_expr,
            output_fields=["uri", "title", "summary", "source", "channel", "date", "url"],
            search_params={"metric_type": "COSINE", "params": {"radius": 0.15}},
        )
        if not results or not results[0]:
            return []

        news_list = []
        for hit in results[0]:
            entity = hit.get("entity", {})
            news_list.append(
                {
                    "uri": entity.get("uri", ""),
                    "title": entity.get("title", ""),
                    "summary": entity.get("summary", ""),
                    "source": entity.get("source", "華爾街見聞"),
                    "channel": entity.get("channel", ""),
                    "date": entity.get("date", ""),
                    "url": entity.get("url", ""),
                    "similarity": round(float(hit.get("distance", 0)), 4),
                }
            )
        logger.info(f"[news_store] 語義檢索「{query[:30]}...」: {len(news_list)} 條")
        return news_list
    except Exception as e:
        logger.warning(f"[news_store] 語義檢索失敗: {e}")
        return []


def cleanup_expired_news() -> int:
    """清理過期新聞（超過 TTL 天數）。

    Returns:
        int: 清理的條數
    """
    _try_init()
    if not _milvus:
        return 0
    if not _ensure_collection():
        return 0

    cutoff_ts = int((datetime.now(tz=timezone.utc) - timedelta(days=_NEWS_TTL_DAYS)).timestamp())
    try:
        # 查詢過期新聞的 ID
        expired = _milvus.query(
            collection_name=COLLECTION_NAME,
            filter=f"timestamp < {cutoff_ts}",
            output_fields=["id"],
            limit=1000,
        )
        if not expired:
            return 0

        # 按 ID 刪除（Milvus Lite 用 ids 刪除）
        ids_to_delete = [item.get("id") for item in expired if item.get("id")]
        if ids_to_delete:
            _milvus.delete(collection_name=COLLECTION_NAME, ids=ids_to_delete)
        logger.info(f"[news_store] 清理過期新聞: {len(ids_to_delete)} 條")
        return len(ids_to_delete)
    except Exception as e:
        logger.warning(f"[news_store] 清理過期新聞失敗: {e}")
        return 0


def dedup_vector_store() -> dict[str, int]:
    """清理向量庫中的重複新聞（保留每個 URI 的第一條，刪除其餘）。

    用於修復歷史重複插入的數據。

    Returns:
        dict: {"total": N, "duplicates_deleted": N, "remaining": N}
    """
    _try_init()
    if not _milvus or not _ensure_collection():
        return {"total": 0, "duplicates_deleted": 0, "remaining": 0}

    try:
        # 查詢所有記錄的 id 和 uri
        all_records = _milvus.query(
            collection_name=COLLECTION_NAME,
            filter="timestamp > 0",
            output_fields=["id", "uri"],
            limit=10000,
        )
        if not all_records:
            return {"total": 0, "duplicates_deleted": 0, "remaining": 0}

        # 按 URI 分組（標準化 URI：取最後一段作為統一 key），找出重複
        uri_to_ids: dict[str, list] = {}
        for record in all_records:
            raw_uri = record.get("uri", "")
            # 標準化 URI：若為完整 URL，取最後一段作為統一 key
            if raw_uri.startswith("http"):
                normalized_uri = raw_uri.rstrip("/").split("/")[-1]
            else:
                normalized_uri = raw_uri
            rid = record.get("id")
            if normalized_uri and rid is not None:
                uri_to_ids.setdefault(normalized_uri, []).append(rid)

        # 對每個 URI，保留第一個 id，其餘標記為待刪除
        ids_to_delete = []
        for uri, ids in uri_to_ids.items():
            if len(ids) > 1:
                ids_to_delete.extend(ids[1:])  # 保留第一個，刪除其餘

        if ids_to_delete:
            _milvus.delete(collection_name=COLLECTION_NAME, ids=ids_to_delete)
            logger.info(
                f"[news_store] 去重清理: 刪除 {len(ids_to_delete)} 條重複，"
                f"保留 {len(all_records) - len(ids_to_delete)} 條"
            )

        # 更新內存快取
        _uri_cache.clear()
        _uri_cache.update(uri_to_ids.keys())

        return {
            "total": len(all_records),
            "duplicates_deleted": len(ids_to_delete),
            "remaining": len(all_records) - len(ids_to_delete),
        }
    except Exception as e:
        logger.warning(f"[news_store] 去重清理失敗: {e}")
        return {"total": 0, "duplicates_deleted": 0, "remaining": 0}


def rebuild_collection() -> bool:
    """刪除並重建向量庫 collection — 用於清理所有歷史數據（含錯誤 URL）。

    Returns:
        bool: 是否成功重建
    """
    global _uri_cache, _uri_cache_loaded
    _try_init()
    if not _milvus:
        return False
    try:
        # 刪除現有 collection
        if _milvus.has_collection(COLLECTION_NAME):
            _milvus.drop_collection(COLLECTION_NAME)
            logger.info(f"[news_store] 已刪除舊 collection: {COLLECTION_NAME}")
        # 清空內存快取
        _uri_cache.clear()
        _uri_cache_loaded = False
        # 重新創建
        if _ensure_collection():
            logger.info(f"[news_store] collection 重建成功: {COLLECTION_NAME}")
            return True
        return False
    except Exception as e:
        logger.warning(f"[news_store] collection 重建失敗: {e}")
        return False


def is_available() -> bool:
    """新聞向量服務是否可用。"""
    _try_init()
    return _milvus is not None and _embedding_model is not None


def get_status() -> dict[str, Any]:
    """獲取新聞向量服務狀態。"""
    return {
        "available": is_available(),
        "collection": COLLECTION_NAME,
        "ttl_days": _NEWS_TTL_DAYS,
        "max_vectors": _MAX_NEWS_VECTORS,
        "init_error": _init_error if _init_fail_count > 0 else "",
    }


async def sync_news_to_vector_store(
    channel: str = "a-stock",
    limit: int = 20,
) -> dict[str, int]:
    """抓取新聞並存入向量庫 + MySQL（用於定時同步任務）。

    Args:
        channel: 頻道
        limit: 抓取條數

    Returns:
        dict: {"fetched": N, "stored": N, "duplicated": N, "failed": N}
    """
    # 抓取新聞
    if channel == "a-stock":
        articles = await wallstreetcn_client.fetch_a_stock_focused(limit=limit)
    else:
        articles = await wallstreetcn_client.fetch_latest_articles(channel, limit=limit)

    # 1. 存入向量庫
    result = store_news_batch(articles)

    # 2. 同時寫入 MySQL（通過 Java 後端 API）
    mysql_result = await _upsert_to_mysql(articles)

    return {
        "fetched": len(articles),
        "stored": result["stored"],
        "duplicated": result["duplicated"],
        "failed": result["failed"],
        "mysql_stored": mysql_result.get("stored", 0),
        "mysql_duplicated": mysql_result.get("duplicated", 0),
    }


async def _upsert_to_mysql(articles: list[dict[str, Any]]) -> dict[str, int]:
    """將新聞批量寫入 MySQL（通過 Java 後端 /api/news/batch 端點）。

    失敗時靜默處理，不影響向量庫同步結果。
    """
    if not articles:
        return {"stored": 0, "duplicated": 0, "failed": 0}
    try:
        import os

        import httpx

        backend_url = os.environ.get(
            "BACKEND_API_URL", "http://localhost:8090/TradingWorkstation"
        )
        items = [
            {
                "uri": a.get("uri", ""),
                "title": a.get("title", ""),
                "summary": a.get("summary", ""),
                "content": a.get("content", ""),
                "source": a.get("source", "華爾街見聞"),
                "author": a.get("author", ""),
                "channel": a.get("channel", ""),
                "date": a.get("date", ""),
                "url": a.get("url", ""),
                "imageUrl": a.get("image_url", ""),
            }
            for a in articles
            if a.get("uri") and a.get("title")
        ]
        if not items:
            return {"stored": 0, "duplicated": 0, "failed": 0}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{backend_url}/api/news/batch",
                json={"items": items},
            )
            resp.raise_for_status()
            data = resp.json()
            result_data = data.get("data", {})
            logger.info(
                f"[news_store] MySQL 寫入: stored={result_data.get('stored', 0)}, "
                f"duplicated={result_data.get('duplicated', 0)}"
            )
            return {
                "stored": result_data.get("stored", 0),
                "duplicated": result_data.get("duplicated", 0),
                "failed": result_data.get("failed", 0),
            }
    except Exception as e:
        logger.warning(f"[news_store] MySQL 寫入失敗（不影響向量庫同步）: {e}")
        return {"stored": 0, "duplicated": 0, "failed": len(articles)}


def format_news_for_prompt(news_list: list[dict[str, Any]], max_items: int = 10) -> str:
    """將新聞列表格式化為可注入 AI prompt 的文本。

    格式：
    ## 華爾街見聞相關新聞（語義檢索）
    [2026-08-23] 標題 (來源: 華爾街見聞, 相似度: 0.85)
      摘要...
      來源: https://wallstreetcn.com/articles/xxx
    """
    if not news_list:
        return ""

    lines = ["## 華爾街見聞相關新聞（語義檢索）"]
    for n in news_list[:max_items]:
        title = n.get("title", "")
        summary = n.get("summary", "")
        source = n.get("source", "華爾街見聞")
        date = n.get("date", "")[:10]
        url = n.get("url", "")
        sim = n.get("similarity", 0)
        lines.append(f"[{date}] {title} (來源: {source}, 相似度: {sim})")
        if summary:
            lines.append(f"  摘要: {summary[:150]}")
        if url:
            lines.append(f"  來源: {url}")
        lines.append("")

    # 引用格式提示（遵守 llms.txt 規範）
    lines.append("引用格式：華爾街見聞，[標題]，[日期]，[URL]")
    return "\n".join(lines)
