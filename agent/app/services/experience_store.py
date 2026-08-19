"""經驗存儲/檢索服務 — 封裝 vector_store，提供高層 API。

職責：
- 每輪優化結束後存儲經驗（市場環境 + 策略 + 結果 + 反思）
- 策略生成前檢索相似歷史經驗
- 格式化經驗為 prompt 可注入的文本
- 自動降級：RAG 不可用時返回空列表，不影響優化循環
"""
import logging
from typing import Any

from app.services import vector_store

logger = logging.getLogger("agent.experience")


def store_iteration_experience(
    iteration: int,
    market_context: str,
    criteria: dict[str, Any],
    stats: dict[str, Any],
    reflection: str,
    composite_score: float,
    timestamp: str = "",
) -> bool:
    """存儲一輪優化的完整經驗到 RAG 向量庫。

    在 optimizer.py 每輪結束後調用。
    """
    return vector_store.store_experience(
        iteration=iteration,
        market_context=market_context,
        criteria=criteria,
        stats=stats,
        reflection=reflection,
        composite_score=composite_score,
        timestamp=timestamp,
    )


def retrieve_relevant_experiences(
    market_context: str,
    current_criteria: dict[str, Any],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """檢索與當前市場環境相似的歷史優化經驗。

    在 AI 2 策略生成前調用，結果注入 prompt。
    """
    return vector_store.search_similar_experiences(
        market_context=market_context,
        current_criteria=current_criteria,
        top_k=top_k,
        min_score=0.3,  # cosine similarity 閾值
    )


def format_experiences_for_prompt(experiences: list[dict[str, Any]]) -> str:
    """將歷史經驗格式化為可注入 prompt 的文本。

    格式：
    ## 歷史相似經驗（RAG 檢索）
    ### 經驗1（第N輪，相似度0.85，評分68.5）
    - 市場環境: ...
    - 策略條件: minTurn=1.5, minReturn20=3.0, ...
    - 回測結果: 收益5.2%, 回撤6.8%, 夏普1.05
    - 反思: 回撤偏高，建議增加止損...
    """
    if not experiences:
        return ""

    lines = ["## 歷史相似經驗（RAG 檢索）"]
    for i, exp in enumerate(experiences, 1):
        sim = exp.get("similarity", 0)
        score = exp.get("composite_score", 0)
        iter_num = exp.get("iteration", 0)
        lines.append(f"### 經驗{i}（第{iter_num}輪，相似度{sim}，評分{score}）")

        # 市場環境（截斷）
        market = exp.get("market_context", "")
        if market:
            lines.append(f"- 市場環境: {market[:150]}")

        # 策略條件（只顯示激活的）
        criteria = exp.get("criteria", {})
        active = {
            k: v for k, v in criteria.items()
            if v is not None and v != False and v != "any" and v != 0
        }
        if active:
            import json
            lines.append(f"- 策略條件: {json.dumps(active, ensure_ascii=False)}")

        # 回測結果
        stats = exp.get("stats", {})
        if stats:
            ret = stats.get("totalReturn", 0)
            dd = stats.get("maxDrawdown", 0)
            sharpe = stats.get("sharpe", 0)
            lines.append(f"- 回測結果: 收益{ret}%, 回撤{dd}%, 夏普{sharpe}")

        # 反思（截斷）
        reflection = exp.get("reflection", "")
        if reflection:
            lines.append(f"- 反思: {reflection[:200]}")

        lines.append("")

    # 添加使用指引
    lines.append("請參考以上歷史經驗：")
    lines.append("- 如果相似市場環境下某策略效果好，可借鑒其參數方向")
    lines.append("- 如果相似市場環境下某策略效果差，避免重複類似錯誤")
    lines.append("- 不要直接複製歷史策略，而是基於反思改進")

    return "\n".join(lines)


def is_rag_available() -> bool:
    """RAG 服務是否可用。"""
    return vector_store.is_available()


def get_rag_status() -> dict[str, Any]:
    """獲取 RAG 狀態。"""
    return vector_store.get_status()
