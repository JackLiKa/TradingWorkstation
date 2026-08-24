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
from app.services.news_filter import filter_mixed_news, filter_news_items

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

            # 復用 vector_store 的鎖清理邏輯
            from app.services.vector_store import _cleanup_stale_lock
            _cleanup_stale_lock(data_dir, db_path)

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


# 利好/利空方向關鍵詞（用於方向敏感的查詢擴展）
_BULLISH_KEYWORDS = {"利好", "利多", "上漲", "反彈", "突破", "超預期", "增長", "景氣", "復甦", "政策支持", "資金流入", "訂單", "量產", "拐點"}
_BEARISH_KEYWORDS = {"利空", "利淡", "下跌", "暴跌", "暴雷", "虧損", "下滑", "收緊", "打壓", "風險", "違約", "退市", "制裁", "資金流出", "減持"}


def _enrich_query_directional(query: str) -> str:
    """方向敏感的查詢擴展 — 利好/利空用不同上下文，避免向量趨同。

    問題：原本「利好」「利空」都被擴展為「財經新聞 A股市場 行業動態」，
    導致兩個方向相反的查詢向量幾乎相同，返回結果也幾乎相同。

    解決：根據查詢中的方向關鍵詞，注入方向特定的上下文：
    - 利好類 → 注入「政策落地 業績超預期 技術突破 資金流入 訂單增長」
    - 利空類 → 注入「業績下滑 政策收緊 風險事件 資金流出 減持違約」
    - 中性   → 注入通用財經上下文
    """
    if len(query) >= 30:
        return query  # 長查詢已有足夠上下文，不擴展

    query_lower = query.lower()
    has_bullish = any(kw in query for kw in _BULLISH_KEYWORDS)
    has_bearish = any(kw in query for kw in _BEARISH_KEYWORDS)

    if has_bullish and not has_bearish:
        # 利好方向：注入利好特徵詞
        return f"{query} 政策落地 業績超預期 技術突破量產 資金持續流入 訂單增長 行業景氣改善"
    elif has_bearish and not has_bullish:
        # 利空方向：注入利空特徵詞
        return f"{query} 業績下滑虧損 政策收緊打壓 風險事件 資金流出減持 違約退市 制裁"
    elif has_bullish and has_bearish:
        # 同時含利好利空：不擴展方向，只加通用上下文
        return f"{query} 財經新聞 A股市場 行業動態"
    else:
        # 中性查詢：通用擴展
        return f"{query} 財經新聞 A股市場 行業動態"


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

    # 向量化查詢（方向敏感擴展：利好/利空用不同上下文，避免向量趨同）
    enriched_query = _enrich_query_directional(query)
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
    limit: int = 50,
) -> dict[str, int]:
    """抓取新聞並存入向量庫 + MySQL（用於定時同步任務）。

    Args:
        channel: 頻道（a-stock/global/all）
        limit: 抓取條數上限（channel=all 時忽略，抓取全量）

    Returns:
        dict: {"fetched": N, "stored": N, "duplicated": N, "failed": N}
    """
    # 抓取新聞
    if channel == "all":
        # 全量同步：所有頻道 + 頭條 + 熱文 + 快訊
        raw_articles = await wallstreetcn_client.fetch_all_channels(limit_per_channel=50)
    elif channel == "a-stock":
        # A 股聚焦：A 股 + 全球 + 快訊 + 熱文
        raw_articles = await wallstreetcn_client.fetch_a_stock_focused(limit=limit)
    else:
        # 單頻道
        raw_articles = await wallstreetcn_client.fetch_latest_articles(channel, limit=limit)

    # 財經關鍵詞過濾 — 丟棄噪音（7x24 快訊無關鍵詞的、廣告、非財經內容）
    fetched_count = len(raw_articles)
    if channel in ("all", "a-stock"):
        articles = filter_mixed_news(raw_articles)
    else:
        articles = filter_news_items(raw_articles, source_type="article")
    filtered_count = fetched_count - len(articles)

    # 1. 存入向量庫
    result = store_news_batch(articles)

    # 2. 同時寫入 MySQL（通過 Java 後端 API）
    mysql_result = await _upsert_to_mysql(articles)

    return {
        "fetched": fetched_count,
        "filtered": filtered_count,
        "stored": result["stored"],
        "duplicated": result["duplicated"],
        "failed": result["failed"],
        "mysql_stored": mysql_result.get("stored", 0),
        "mysql_duplicated": mysql_result.get("duplicated", 0),
    }


async def catchup_news(
    channels: list[str] | None = None,
    catchup_days: int = 7,
    max_pages_per_channel: int = 20,
) -> dict[str, Any]:
    """啟動時補抓漏掉的新聞（cursor 分頁追回歷史數據）。

    用於系統啟動時追回停機期間漏掉的新聞。
    從最新開始往回翻頁，遇到已存在的 URI 或超過 cutoff_date 時停止。

    Args:
        channels: 要補抓的頻道列表（None = 全頻道）
        catchup_days: 補抓天數（往前追 N 天的新聞）
        max_pages_per_channel: 每個頻道最多翻頁數

    Returns:
        {"channels": N, "fetched": N, "stored": N, "duplicated": N, "failed": N,
         "mysql_stored": N, "mysql_duplicated": N, "duration_seconds": N}
    """
    import time as _time
    from datetime import datetime, timedelta, timezone

    start = _time.time()

    if channels is None:
        channels = ["a-stock", "global", "us-stock", "hk-stock", "forex", "commodity"]

    # 計算截止日期
    cutoff_dt = datetime.now(tz=timezone.utc) - timedelta(days=catchup_days)
    cutoff_date = cutoff_dt.strftime("%Y-%m-%d")
    logger.info(f"[news_store] 補抓新聞: {channels}, 截止日期={cutoff_date}, 每頻道最多 {max_pages_per_channel} 頁")

    # 獲取已存在的 URI 集合（從向量庫 URI cache）
    _try_init()
    _load_uri_cache()
    existing_set = set(_uri_cache)
    logger.info(f"[news_store] 已有 {len(existing_set)} 個 URI 用於去重")

    all_articles: list[dict[str, Any]] = []
    seen_uris: set[str] = set()

    for channel in channels:
        try:
            articles = await wallstreetcn_client.fetch_articles_catchup(
                channel=channel,
                max_pages=max_pages_per_channel,
                existing_uris=existing_set,
                cutoff_date=cutoff_date,
            )
            for a in articles:
                uri = a.get("uri", "")
                if uri and uri not in seen_uris:
                    seen_uris.add(uri)
                    all_articles.append(a)
        except Exception as e:
            logger.warning(f"[news_store] 補抓頻道 {channel} 失敗: {e}")

    if not all_articles:
        logger.info("[news_store] 補抓完成: 無新新聞")
        return {
            "channels": len(channels),
            "fetched": 0,
            "filtered": 0,
            "stored": 0,
            "duplicated": 0,
            "failed": 0,
            "mysql_stored": 0,
            "mysql_duplicated": 0,
            "duration_seconds": round(_time.time() - start, 1),
        }

    # 財經關鍵詞過濾 — 補抓的新聞也需要過濾噪音
    fetched_count = len(all_articles)
    all_articles = filter_news_items(all_articles, source_type="article")
    filtered_count = fetched_count - len(all_articles)
    if filtered_count > 0:
        logger.info(f"[news_store] 補抓新聞過濾: {fetched_count} → {len(all_articles)} 條（丟棄 {filtered_count} 條噪音）")

    # 存入向量庫
    result = store_news_batch(all_articles)

    # 寫入 MySQL
    mysql_result = await _upsert_to_mysql(all_articles)

    duration = round(_time.time() - start, 1)
    logger.info(
        f"[news_store] 補抓完成: {len(all_articles)} 條新新聞, "
        f"向量庫 stored={result['stored']}, MySQL stored={mysql_result.get('stored', 0)}, "
        f"耗時 {duration}s"
    )

    return {
        "channels": len(channels),
        "fetched": fetched_count,
        "filtered": filtered_count,
        "stored": result["stored"],
        "duplicated": result["duplicated"],
        "failed": result["failed"],
        "mysql_stored": mysql_result.get("stored", 0),
        "mysql_duplicated": mysql_result.get("duplicated", 0),
        "duration_seconds": duration,
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


# ===== 新聞情感評分持久化（利好/利空池）=====


async def save_sentiment_scores(
    scores: list[dict[str, Any]],
    query_context: str = "",
) -> dict[str, int]:
    """將 reranker 評分結果批量寫入 MySQL（news_sentiment_score 表）。

    用於建立「利好池」「利空池」，策略生成時只從利好池選股。
    自我成長機制：每次評分都持久化，歷史評分可復用。

    Args:
        scores: 評分列表，每項含 uri/title/direction/sustainability/composite_score/news_label
        query_context: 評分時的查詢上下文

    Returns:
        {"stored": N, "duplicated": N, "failed": N}
    """
    if not scores:
        return {"stored": 0, "duplicated": 0, "failed": 0}
    try:
        import os

        import httpx

        backend_url = os.environ.get(
            "BACKEND_API_URL", "http://localhost:8090/TradingWorkstation"
        )
        items = [
            {
                "uri": s.get("uri", ""),
                "title": s.get("title", ""),
                "direction": s.get("direction", 0),
                "sustainability": s.get("sustainability", 0),
                "compositeScore": s.get("composite_score", 0),
                "newsLabel": s.get("news_label", "中性"),
                "queryContext": query_context[:500],
            }
            for s in scores
            if s.get("uri") and s.get("title")
        ]
        if not items:
            return {"stored": 0, "duplicated": 0, "failed": 0}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{backend_url}/api/news/sentiment/batch",
                json={"items": items},
            )
            resp.raise_for_status()
            data = resp.json()
            result_data = data.get("data", {})
            logger.info(
                f"[news_store] 情感評分寫入: stored={result_data.get('stored', 0)}, "
                f"duplicated={result_data.get('duplicated', 0)}"
            )
            return {
                "stored": result_data.get("stored", 0),
                "duplicated": result_data.get("duplicated", 0),
                "failed": result_data.get("failed", 0),
            }
    except Exception as e:
        logger.warning(f"[news_store] 情感評分寫入失敗（不影響 reranker）: {e}")
        return {"stored": 0, "duplicated": 0, "failed": len(scores)}


async def get_bullish_pool(
    days_back: int = 7,
    min_direction: int = 5,
    min_sustainability: int = 6,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """獲取利好池 — 持續性利好新聞（direction >= 5 且 sustainability >= 6）。

    策略生成時從此池選股，確保只選有持續性利好支撐的標的。

    Args:
        days_back: 只檢索最近 N 天的評分
        min_direction: 最低方向分（默認 5 = 中度利好以上）
        min_sustainability: 最低持續性分（默認 6 = 中度持續以上）
        limit: 返回條數

    Returns:
        利好新聞列表，每項含 uri/title/direction/sustainability/news_label/scored_at
    """
    try:
        import os

        import httpx

        backend_url = os.environ.get(
            "BACKEND_API_URL", "http://localhost:8090/TradingWorkstation"
        )
        params = {
            "daysBack": days_back,
            "minDirection": min_direction,
            "minSustainability": min_sustainability,
            "limit": limit,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{backend_url}/api/news/sentiment/bullish",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            # 後端返回 ApiResponse<List<...>>，data 字段直接是列表
            raw = data.get("data", [])
            items = raw if isinstance(raw, list) else raw.get("items", [])
            logger.info(f"[news_store] 利好池查詢: {len(items)} 條持續性利好")
            return items
    except Exception as e:
        logger.warning(f"[news_store] 利好池查詢失敗: {e}")
        return []


async def get_bearish_pool(
    days_back: int = 7,
    min_abs_direction: int = 5,
    min_sustainability: int = 6,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """獲取利空池 — 持續性利空新聞（direction <= -5 且 sustainability >= 6）。

    策略生成時用此池排除利空行業/個股。

    Args:
        days_back: 只檢索最近 N 天的評分
        min_abs_direction: 最低絕對方向分（默認 5）
        min_sustainability: 最低持續性分（默認 6）
        limit: 返回條數

    Returns:
        利空新聞列表
    """
    try:
        import os

        import httpx

        backend_url = os.environ.get(
            "BACKEND_API_URL", "http://localhost:8090/TradingWorkstation"
        )
        params = {
            "daysBack": days_back,
            "minAbsDirection": min_abs_direction,
            "minSustainability": min_sustainability,
            "limit": limit,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{backend_url}/api/news/sentiment/bearish",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            # 後端返回 ApiResponse<List<...>>，data 字段直接是列表
            raw = data.get("data", [])
            items = raw if isinstance(raw, list) else raw.get("items", [])
            logger.info(f"[news_store] 利空池查詢: {len(items)} 條持續性利空")
            return items
    except Exception as e:
        logger.warning(f"[news_store] 利空池查詢失敗: {e}")
        return []


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
