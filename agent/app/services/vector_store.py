"""向量存儲服務 — Milvus Lite 嵌入式模式 + sentence-transformers 中文 embedding。

用於 RAG 歷史經驗回憶：
- 每輪優化結束後，將「市場環境 + 策略條件 + 回測結果 + 反思」向量化存入 Milvus
- 下一輪策略生成前，用當前市場狀態做語義搜索，返回相似歷史經驗
- 注入到 AI 2 策略生成 prompt 的「歷史經驗」部分

設計要點：
- Milvus Lite 嵌入式模式（無需獨立服務，數據存本地文件）
- BAAI/bge-small-zh-v1.5 中文 embedding 模型（95MB，本地運行，無 API 成本）
- 自動降級：Milvus/embedding 不可時靜默跳過，不影響優化循環
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("agent.rag")


def _cleanup_stale_lock(data_dir: Path, db_path: str) -> None:
    """清理 Milvus Lite 殘留鎖文件。

    Milvus Lite 使用 msvcrt.locking（Windows）或 fcntl（Linux）做文件鎖。
    Agent 異常退出（kill -9、崩潰）後鎖文件可能殘留，導致下次啟動時
    DataDirLockedError: another process holds the lock。

    策略：檢查 .lock 文件的最後修改時間，超過 60 秒未修改則視為殘留並刪除。
    正在運行的進程會持續更新鎖文件，不會誤刪。
    """
    lock_file = data_dir / "milvus_lite.db.lock"
    if not lock_file.exists():
        return
    try:
        mtime = lock_file.stat().st_mtime
        age = time.time() - mtime
        if age > 60:
            lock_file.unlink(missing_ok=True)
            logger.info(f"Milvus: 清理殘留鎖文件（年齡 {age:.0f}s）: {lock_file}")
    except Exception as e:
        logger.debug(f"Milvus: 鎖文件清理檢查失敗（非致命）: {e}")

# ===== 配置 =====
_MAX_EXPERIENCES = int(os.environ.get("RAG_MAX_EXPERIENCES", "1000"))  # 最多保留經驗數
_DEDUP_SIMILARITY_THRESHOLD = float(os.environ.get("RAG_DEDUP_THRESHOLD", "0.98"))  # 去重相似度閾值

# 延遲導入 — Milvus 和 sentence-transformers 是可選依賴
_milvus = None
_embedding_model = None
_init_attempted = False
_init_error = ""
_init_fail_count = 0
_last_init_attempt_time = 0.0
_MAX_INIT_RETRIES = 3  # 最多重試 3 次，避免永久放棄
_INIT_RECOVERY_SECONDS = 300  # 熔斷恢復時間：5 分鐘後允許重試


def _try_init():
    """延遲初始化 Milvus 和 embedding 模型（首次使用時）。

    若初始化失敗，允許重試最多 _MAX_INIT_RETRIES 次，
    達上限後進入熔斷狀態，_INIT_RECOVERY_SECONDS 後自動允許重試。
    """
    global _milvus, _embedding_model, _init_attempted, _init_error, _init_fail_count, _last_init_attempt_time
    import time as _time
    # 熔斷恢復檢查：超過恢復時間則重置計數，允許重試
    if _init_attempted and _init_fail_count >= _MAX_INIT_RETRIES:
        if _time.time() - _last_init_attempt_time < _INIT_RECOVERY_SECONDS:
            return  # 仍在熔斷期
        # 恢復時間已過，重置計數允許重試
        _init_fail_count = 0
        logger.info(f"RAG: 熔斷恢復，重置初始化計數，允許重試")
    if _init_attempted and _milvus is not None and _embedding_model is not None:
        return  # 已成功初始化
    _init_attempted = True
    _last_init_attempt_time = _time.time()

    try:
        from pymilvus import MilvusClient

        # 數據存儲路徑（agent/data/milvus_lite.db）
        data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        db_path = str(data_dir / "milvus_lite.db")

        # 清理殘留鎖文件（Agent 異常退出後可能留下 .lock 文件導致下次啟動失敗）
        _cleanup_stale_lock(data_dir, db_path)

        _milvus = MilvusClient(db_path)
        logger.info(f"Milvus Lite 初始化成功: {db_path}")
    except Exception as e:
        _init_fail_count += 1
        _init_error = f"Milvus 初始化失敗 (第{_init_fail_count}次): {e}"
        logger.warning(_init_error)
        return

    try:
        from sentence_transformers import SentenceTransformer

        # bge-small-zh-v1.5: 95MB, 512 維, 中文優化, 本地運行
        model_name = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
        _embedding_model = SentenceTransformer(model_name)
        logger.info(f"Embedding 模型載入成功: {model_name}")
        _init_fail_count = 0  # 成功則重置計數
    except Exception as e:
        _init_fail_count += 1
        _init_error = f"Embedding 模型載入失敗 (第{_init_fail_count}次): {e}"
        logger.warning(_init_error)
        _milvus = None  # 沒有 embedding 就無法使用 RAG


COLLECTION_NAME = "optimization_experiences"
EMBEDDING_DIM = 512  # bge-small-zh-v1.5 輸出維度


def _ensure_collection():
    """確保 Milvus collection 存在。"""
    if not _milvus:
        return False
    try:
        from pymilvus import DataType

        if _milvus.has_collection(COLLECTION_NAME):
            return True
        # 創建 collection schema
        schema = _milvus.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
        schema.add_field("iteration", DataType.INT64)
        schema.add_field("market_context", DataType.VARCHAR, max_length=2000)
        schema.add_field("criteria_json", DataType.VARCHAR, max_length=4000)
        schema.add_field("result_json", DataType.VARCHAR, max_length=2000)
        schema.add_field("reflection", DataType.VARCHAR, max_length=2000)
        schema.add_field("composite_score", DataType.FLOAT)
        schema.add_field("timestamp", DataType.VARCHAR, max_length=50)

        index_params = _milvus.prepare_index_params()
        index_params.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE")
        _milvus.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )
        logger.info(f"Milvus collection 創建: {COLLECTION_NAME}")
        return True
    except Exception as e:
        logger.warning(f"Milvus collection 創建失敗: {e}")
        return False


def _embed(text: str) -> list[float] | None:
    """將文本轉為向量。"""
    if not _embedding_model:
        return None
    try:
        vec = _embedding_model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        logger.warning(f"Embedding 失敗: {e}")
        return None


def _build_experience_text(
    market_context: str,
    criteria: dict[str, Any],
    stats: dict[str, Any],
    reflection: str,
) -> str:
    """構建用於 embedding 的經驗文本（語義豐富的描述）。"""
    # 提取關鍵策略特徵
    active_filters = {k: v for k, v in criteria.items() if v is not None and v is not False and v != "any" and v != 0}
    # 提取行業聚焦信息（顯式加入語義文本，提升行業相關經驗的檢索質量）
    industries = criteria.get("industries")
    industry_text = ""
    if industries and isinstance(industries, list) and len(industries) > 0:
        industry_text = f"\n行業聚焦: {', '.join(industries)}"
    # 提取回測結果摘要
    total_return = stats.get("totalReturn", 0)
    max_drawdown = stats.get("maxDrawdown", 0)
    sharpe = stats.get("sharpe", 0)
    # 構建語義文本（包含市場環境 + 策略特徵 + 行業聚焦 + 結果）
    text = (
        f"市場環境: {market_context[:300]}\n"
        f"策略條件: {json.dumps(active_filters, ensure_ascii=False)}"
        f"{industry_text}\n"
        f"回測結果: 收益{total_return}%, 回撤{max_drawdown}%, 夏普{sharpe}\n"
        f"反思: {reflection[:200]}"
    )
    return text


def is_available() -> bool:
    """RAG 服務是否可用。"""
    _try_init()
    return _milvus is not None and _embedding_model is not None


def _compute_content_hash(
    market_context: str,
    criteria: dict[str, Any],
    stats: dict[str, Any],
) -> str:
    """計算經驗內容的確定性哈希（用於精確去重）。

    只取關鍵字段計算，忽略 reflection（反思文本每次不同但策略可能相同）。
    """
    active_filters = {
        k: v for k, v in sorted(criteria.items()) if v is not None and v is not False and v != "any" and v != 0
    }
    key_parts = [
        market_context[:500],  # 市場環境摘要
        json.dumps(active_filters, ensure_ascii=False, sort_keys=True),
        json.dumps({k: stats.get(k, 0) for k in ["totalReturn", "maxDrawdown", "sharpe"]}, ensure_ascii=False),
    ]
    return hashlib.sha256("|".join(key_parts).encode("utf-8")).hexdigest()[:16]


def _check_near_duplicate(embedding: list[float], composite_score: float) -> bool:
    """檢查是否已存在近似重複的經驗（高相似度 + 相近分數）。

    Args:
        embedding: 待插入經驗的向量
        composite_score: 綜合評分

    Returns:
        bool: True 表示已存在近似重複，應跳過插入
    """
    if not _milvus:
        return False
    try:
        results = _milvus.search(
            collection_name=COLLECTION_NAME,
            data=[embedding],
            limit=1,
            output_fields=["composite_score"],
            search_params={"metric_type": "COSINE", "params": {"radius": _DEDUP_SIMILARITY_THRESHOLD}},
        )
        if results and results[0]:
            hit = results[0][0]
            score = hit.get("distance", 0)
            existing_score = hit.get("entity", {}).get("composite_score", 0)
            if score >= _DEDUP_SIMILARITY_THRESHOLD:
                # 如果新經驗分數更高，允許插入（會在後續清理中保留更好的）
                if composite_score > existing_score:
                    logger.info(
                        f"RAG: 檢測到近似重複 (sim={score:.3f}) 但新分數更高 ({composite_score} > {existing_score})，允許插入"
                    )
                    return False
                logger.info(f"RAG: 跳過近似重複經驗 (sim={score:.3f}, score={existing_score})")
                return True
    except Exception as e:
        logger.debug(f"RAG 去重檢查失敗（忽略，繼續插入）: {e}")
    return False


def _enforce_retention():
    """執行保留策略：當經驗數超過上限時，刪除低分舊經驗。"""
    if not _milvus:
        return
    try:
        # 查詢當前記錄數
        stats = _milvus.get_collection_stats(COLLECTION_NAME)
        count = stats.get("row_count", 0)
        if count <= _MAX_EXPERIENCES:
            return
        # 需要刪除的數量
        to_delete = count - _MAX_EXPERIENCES
        logger.info(f"RAG: 經驗數 {count} 超過上限 {_MAX_EXPERIENCES}，清理 {to_delete} 條低分舊經驗")
        # 先嘗試清理負分經驗（明顯失敗的），不足時清理最低分正分經驗
        results = _milvus.query(
            collection_name=COLLECTION_NAME,
            filter="composite_score < 0",  # 優先清理負分
            output_fields=["id"],
            limit=to_delete,
        )
        ids_to_delete = [r["id"] for r in results if "id" in r] if results else []
        # 若負分經驗不足，補充清理最低分正分經驗
        remaining = to_delete - len(ids_to_delete)
        if remaining > 0:
            positive_results = _milvus.query(
                collection_name=COLLECTION_NAME,
                filter="composite_score >= 0",  # 正分經驗中最低分
                output_fields=["id", "composite_score"],
                limit=remaining,
            )
            if positive_results:
                # 按 composite_score 升序排序，取最低分
                positive_results.sort(key=lambda r: r.get("composite_score", 0))
                ids_to_delete.extend(r["id"] for r in positive_results if "id" in r)
        if ids_to_delete:
            _milvus.delete(collection_name=COLLECTION_NAME, ids=ids_to_delete)
            logger.info(f"RAG: 已清理 {len(ids_to_delete)} 條低分經驗")
    except Exception as e:
        logger.debug(f"RAG 保留策略執行失敗（忽略）: {e}")


def store_experience(
    iteration: int,
    market_context: str,
    criteria: dict[str, Any],
    stats: dict[str, Any],
    reflection: str,
    composite_score: float,
    timestamp: str = "",
) -> bool:
    """存儲一輪優化經驗到向量數據庫。

    含去重邏輯：插入前檢查是否已存在近似重複經驗（高相似度 + 相近分數）。
    若新經驗分數更高則允許插入（後續清理保留更好的）。

    Args:
        iteration: 迭代輪次
        market_context: 市場環境分析文本
        criteria: 選股條件
        stats: 回測統計
        reflection: 回測反思結論
        composite_score: 綜合評分
        timestamp: 時間戳

    Returns:
        bool: 是否存儲成功
    """
    _try_init()
    if not is_available():
        return False

    if not _ensure_collection():
        return False

    try:
        # 構建經驗文本並 embedding
        experience_text = _build_experience_text(market_context, criteria, stats, reflection)
        embedding = _embed(experience_text)
        if embedding is None:
            return False

        # 去重檢查：近似重複且分數不高時跳過
        if _check_near_duplicate(embedding, composite_score):
            return True  # 視為成功（已存在等效經驗）

        # 截斷字段以適應 Milvus VARCHAR 限制
        from datetime import datetime

        _milvus.insert(
            collection_name=COLLECTION_NAME,
            data=[
                {
                    "embedding": embedding,
                    "iteration": iteration,
                    "market_context": market_context[:2000],
                    "criteria_json": json.dumps(criteria, ensure_ascii=False)[:4000],
                    "result_json": json.dumps(stats, ensure_ascii=False)[:2000],
                    "reflection": reflection[:2000],
                    "composite_score": composite_score,
                    "timestamp": timestamp or datetime.now().isoformat(),
                }
            ],
        )
        logger.info(f"RAG: 已存儲第 {iteration} 輪經驗 (score={composite_score})")

        # 執行保留策略
        _enforce_retention()
        return True
    except Exception as e:
        logger.warning(f"RAG 存儲經驗失敗: {e}")
        return False


def search_similar_experiences(
    market_context: str,
    current_criteria: dict[str, Any],
    top_k: int = 3,
    min_score: float = 0.5,
    min_composite_score: float = 0.0,
) -> list[dict[str, Any]]:
    """搜索與當前市場環境相似的歷史優化經驗。

    支持業務級過濾：只返回 composite_score >= min_composite_score 的經驗，
    避免返回明顯失敗的策略作為參考。

    Args:
        market_context: 當前市場環境分析
        current_criteria: 當前選股條件（用於構建查詢語義）
        top_k: 返回 top_k 條最相似經驗
        min_score: 最低相似度閾值（cosine similarity）
        min_composite_score: 最低綜合評分閾值（過濾失敗策略）

    Returns:
        list[dict]: 歷史經驗列表，每項含 iteration/criteria/result/reflection/score
    """
    _try_init()
    if not is_available():
        return []

    if not _ensure_collection():
        return []

    try:
        # 構建查詢文本（市場環境 + 當前策略特徵 + 當前行業聚焦）
        active_filters = {
            k: v for k, v in current_criteria.items() if v is not None and v is not False and v != "any" and v != 0
        }
        # 顯式加入當前行業聚焦，提升同行業歷史經驗的檢索優先級
        current_industries = current_criteria.get("industries")
        industry_text = ""
        if current_industries and isinstance(current_industries, list) and len(current_industries) > 0:
            industry_text = f"\n當前行業聚焦: {', '.join(current_industries)}"
        query_text = (
            f"市場環境: {market_context[:300]}\n"
            f"策略條件: {json.dumps(active_filters, ensure_ascii=False)}"
            f"{industry_text}"
        )
        query_embedding = _embed(query_text)
        if query_embedding is None:
            return []

        # 構建業務過濾表達式（只返回分數達標的經驗）
        filter_expr = f"composite_score >= {min_composite_score}" if min_composite_score > 0 else ""

        # 搜索相似經驗
        search_kwargs = {
            "collection_name": COLLECTION_NAME,
            "data": [query_embedding],
            "limit": top_k,
            "output_fields": [
                "iteration",
                "market_context",
                "criteria_json",
                "result_json",
                "reflection",
                "composite_score",
                "timestamp",
            ],
            "search_params": {"metric_type": "COSINE", "params": {"radius": min_score}},
        }
        if filter_expr:
            search_kwargs["filter"] = filter_expr

        results = _milvus.search(**search_kwargs)

        if not results or not results[0]:
            return []

        experiences = []
        for hit in results[0]:
            entity = hit.get("entity", {})
            score = hit.get("distance", 0)
            if score < min_score:
                continue
            try:
                criteria = json.loads(entity.get("criteria_json", "{}"))
                stats = json.loads(entity.get("result_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                continue
            experiences.append(
                {
                    "iteration": entity.get("iteration", 0),
                    "similarity": round(score, 3),
                    "market_context": entity.get("market_context", ""),
                    "criteria": criteria,
                    "stats": stats,
                    "reflection": entity.get("reflection", ""),
                    "composite_score": entity.get("composite_score", 0),
                }
            )

        logger.info(f"RAG: 搜索到 {len(experiences)} 條相似經驗 (top_k={top_k}, min_score={min_composite_score})")
        return experiences
    except Exception as e:
        logger.warning(f"RAG 搜索經驗失敗: {e}")
        return []


def get_status() -> dict[str, Any]:
    """獲取 RAG 服務狀態（用於健康檢查）。"""
    _try_init()
    return {
        "available": is_available(),
        "milvus_connected": _milvus is not None,
        "embedding_model_loaded": _embedding_model is not None,
        "init_error": _init_error,
        "init_fail_count": _init_fail_count,
        "collection": COLLECTION_NAME if _milvus else "",
        "max_experiences": _MAX_EXPERIENCES,
        "dedup_threshold": _DEDUP_SIMILARITY_THRESHOLD,
    }
