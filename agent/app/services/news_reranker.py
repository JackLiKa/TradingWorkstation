"""新聞 LLM 重排序服務 — TopK 初篩 + 大模型雙維度重排。

解決問題：
- 純向量搜索對「利好」「利空」等情感方向詞區分能力弱
  （bge-small 把「利好」「利空」都映射到「財經新聞」語義空間附近）
- 用戶真正需要的不是簡單的利好/利空分類，而是判斷：
  - 哪些是**有持續性的真利好**（政策落地、業績拐點、技術突破、持續資金流入）
  - 哪些是**不可持續的一日遊行情**（概念炒作、傳聞預期、題材輪動、脈衝資金）

雙維度評分體系：
1. **direction**（-10 到 +10）：利好/利空方向
   - +7~+10：強利好（重大政策落地、業績超預期、技術突破）
   - +3~+6：中度利好（行業數據改善、訂單增長）
   - -3~+3：中性（信息中性、方向不明）
   - -6~-3：中度利空（業績下滑、政策收緊）
   - -10~-7：強利空（重大風險事件、業績暴雷）
2. **sustainability**（0-10）：持續性評分
   - 8-10：高持續性（政策落地+執行時間表、業績拐點、技術突破量產、長期資金流入）
   - 5-7：中度持續（行業景氣改善、訂單周期、季度業績支撐）
   - 2-4：低持續性（短期事件、季節性因素、階段性政策）
   - 0-2：一日遊（概念炒作無業績、傳聞無落地、純資金推動、題材輪動）

綜合分數 = direction × sustainability / 10
- 持續性利好（direction>0, sustainability>=6）：高綜合分
- 一日遊利好（direction>0, sustainability<4）：綜合分被持續性壓低
- 持續性利空（direction<0, sustainability>=6）：負分且持續
- 一日遊利空（direction<0, sustainability<4）：負分但短暫

分類標籤：
- "持續性利好"：direction >= 5 且 sustainability >= 6
- "一日遊利好"：direction >= 5 且 sustainability < 4
- "弱利好"：0 < direction < 5
- "中性"：|direction| <= 3
- "弱利空"：-5 < direction <= -3
- "持續性利空"：direction <= -5 且 sustainability >= 6
- "一日遊利空"：direction <= -5 且 sustainability < 4

流程：
1. 向量搜索取 top_k * candidate_multiplier 候選（初篩，召回更多保證召回率）
2. LLM 對每條候選新聞雙維度評分（direction + sustainability）
3. 按綜合分數排序，返回 top_k 條，每條附帶分類標籤

降級策略：
- LLM 不可用 → 返回向量搜索原結果
- LLM 返回格式異常 → 嘗試解析部分結果，失敗則返回原結果
"""

import json
import logging
from typing import Any

logger = logging.getLogger("agent.news_reranker")


_RERANK_SYSTEM_PROMPT = """你是頂級超短線投資者的新聞分析助手，專注判斷新聞的「方向」和「持續性」。

任務：根據用戶查詢意圖，對候選新聞逐條評估兩個維度。

## 維度1：direction（-10 到 +10，整數）— 利好/利空方向
- +8~+10：強利好 — 重大政策落地（有執行時間表）、業績超預期、技術突破量產、行業拐點
- +5~+7：中度利好 — 行業數據改善、訂單增長、政策支持方向明確
- +2~+4：弱利好 — 偏正面但影響有限
- -2~+2：中性 — 信息中性、方向不明、影響兩可
- -4~-3：弱利空 — 偏負面但影響有限
- -7~-5：中度利空 — 業績下滑、政策收緊、行業數據惡化
- -10~-8：強利空 — 重大風險事件、業績暴雷、政策打壓

## 維度2：sustainability（0-10，整數）— 持續性評分（最關鍵維度）
這是區分「真持續利好」與「一日遊炒作」的核心。

### 高持續性（8-10）特徵：
- 政策類：已正式發文+有執行時間表+有資金配套（如「財政部發文，Q4開始執行，500億配套」）
- 業績類：季度業績拐點+管理層指引+行業景氣度同步改善
- 技術類：技術突破+量產時間表+客戶訂單（如「5nm量產，Q4出貨，客戶已下單」）
- 資金類：持續多日資金流入+機構調研+龍頭帶動產業鏈
- 供需類：供需缺口持續擴大+庫存周期反轉（至少2-3個季度）

### 中度持續（5-7）特徵：
- 行業景氣改善但無明確拐點
- 訂單增長但周期性（季度級別）
- 政策支持但執行細節待明確
- 季度業績支撐但未見趨勢反轉

### 低持續性（2-4）特徵：
- 短期事件驅動（展會、簽約、訪問）
- 季節性因素（節假日消費、年終結算）
- 階段性政策（短期補貼、臨時措施）
- 個股利好但無行業效應

### 一日遊（0-2）特徵（必須識別出來）：
- 概念炒作無實質業績（「AI概念」「元宇宙概念」但無產品無營收）
- 傳聞/預期無落地（「據傳」「市場猜測」「知情人士透露」）
- 純資金推動無基本面（龍虎榜遊資接力、漲停板戰法）
- 題材輪動無持續性（板塊輪動、補漲邏輯）
- 一日漲停後無續航（首板無二板、情緒脈衝）
- 舊聞重發/標題黨（無新信息增量）

## 評分原則
1. **寧可低估持續性，不可高估**：一日遊行情佔A股新聞70%以上，默認持續性偏低
2. **看實質不看標題**：「XX行業迎利好」是標題黨，要看具體政策/業績/訂單
3. **看落地不看預期**：「規劃中」「據傳」「或將」持續性極低
4. **看產業鏈不看個股**：單個公司利好無行業效應→持續性低
5. **查詢方向匹配**：若查詢含「利好/看多」，方向相反的新聞綜合分應為負

## 邊界案例處理規則
- **多主題新聞**：取與查詢最相關的主題評分，忽略無關部分
- **模糊新聞**：方向不明時 direction=0，持續性按最壞情況估計（偏低）
- **重複新聞**：內容高度相似的新聞給相同評分
- **舊聞新發**：日期超過3天的新聞持續性降至 0-2（信息已被市場消化）

## 輸出格式（嚴格遵守）
- 只輸出一個 JSON 數組，不要輸出任何其他文字、解釋或 markdown 標記
- 不要在 JSON 前後添加任何自然語言
- reason 字段限制在 30 字以內，只寫關鍵判斷依據
- 每條新聞的 id 必須與輸入序號對應
- 必須覆蓋所有候選新聞，不可遺漏

輸出格式示例：
[{"id": 0, "direction": 8, "sustainability": 9, "label": "持續性利好", "reason": "財政部發文Q4執行500億配套"}, {"id": 1, "direction": -3, "sustainability": 2, "label": "一日遊利空", "reason": "傳聞無落地來源不明"}]"""


def _classify_news(direction: float, sustainability: float) -> str:
    """根據方向和持續性分類新聞。

    Returns:
        分類標籤：持續性利好/一日遊利好/弱利好/中性/弱利空/持續性利空/一日遊利空
    """
    if direction >= 5 and sustainability >= 6:
        return "持續性利好"
    if direction >= 5 and sustainability < 4:
        return "一日遊利好"
    if direction > 3:
        return "弱利好"
    if direction <= -5 and sustainability >= 6:
        return "持續性利空"
    if direction <= -5 and sustainability < 4:
        return "一日遊利空"
    if direction < -3:
        return "弱利空"
    return "中性"


def _build_rerank_prompt(query: str, candidates: list[dict[str, Any]]) -> str:
    """構建重排序 prompt。"""
    lines = [f"用戶查詢：{query}", "", "候選新聞："]

    for i, n in enumerate(candidates):
        title = n.get("title", "")
        summary = n.get("summary", "")[:300]
        date = n.get("date", "")[:10]
        channel = n.get("channel", "")
        lines.append(f"[{i}] 日期={date} 頻道={channel}")
        lines.append(f"    標題：{title}")
        if summary:
            lines.append(f"    摘要：{summary}")
        lines.append("")

    lines.append("請對上述候選新聞逐條評估 direction 和 sustainability。")
    lines.append("只輸出 JSON 數組，不要輸出任何其他文字。格式：")
    lines.append(
        '[{"id": 0, "direction": 8, "sustainability": 9, "label": "持續性利好", "reason": "30字內理由"}, ...]'
    )
    lines.append("id 對應候選新聞的序號，必須覆蓋所有候選，不可遺漏。")
    lines.append("direction 範圍 -10 到 +10 整數，sustainability 範圍 0-10 整數。")
    lines.append("reason 限制 30 字以內，只寫關鍵判斷依據。")
    return "\n".join(lines)


def _parse_rerank_response(
    text: str, count: int
) -> list[dict[str, Any]] | None:
    """解析 LLM 重排序響應（雙維度版本）。

    Returns:
        [{"id": int, "direction": float, "sustainability": float, "label": str, "reason": str}, ...]
        或 None（解析失敗）
    """
    if not text:
        return None

    # 嘗試剝離 markdown code fence
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.find("\n")
        if first_nl > 0:
            cleaned = cleaned[first_nl + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # 嘗試定位第一個 [ 到最後一個 ]
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                logger.warning(f"[news_reranker] JSON 解析失敗: {cleaned[:200]}")
                return None
        else:
            logger.warning(f"[news_reranker] 響應無 JSON 數組: {cleaned[:200]}")
            return None

    if not isinstance(data, list):
        return None

    results: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cid = item.get("id")
        direction = item.get("direction")
        sustainability = item.get("sustainability")
        if cid is None or direction is None or sustainability is None:
            continue
        try:
            cid_int = int(cid)
            direction_float = float(direction)
            sustainability_float = float(sustainability)
        except (TypeError, ValueError):
            continue
        # 範圍校驗
        direction_float = max(-10.0, min(10.0, direction_float))
        sustainability_float = max(0.0, min(10.0, sustainability_float))
        if 0 <= cid_int < count:
            label = item.get("label", "") or _classify_news(direction_float, sustainability_float)
            reason = item.get("reason", "")
            results.append(
                {
                    "id": cid_int,
                    "direction": direction_float,
                    "sustainability": sustainability_float,
                    "label": label,
                    "reason": reason,
                }
            )

    if not results:
        return None
    return results


def _composite_score(direction: float, sustainability: float) -> float:
    """計算綜合分數 = direction × sustainability / 10。

    持續性利好：高正分
    一日遊利好：正分但被持續性壓低
    持續性利空：高負分
    一日遊利空：負分但被持續性壓低
    """
    return round(direction * sustainability / 10, 2)


async def rerank_news(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 10,
    preferred_provider: str = "",
) -> list[dict[str, Any]]:
    """對候選新聞進行 LLM 雙維度重排序。

    Args:
        query: 用戶查詢（如「半導體行業利好」「A股市場利空」）
        candidates: 向量搜索初篩候選新聞列表
        top_k: 返回條數
        preferred_provider: 首選 LLM 供應商（空字串時用階段默認：ox-alpha 推理模型）

    Returns:
        重排序後的新聞列表（前 top_k 條），每項新增：
        - rerank_score: 綜合分數（direction × sustainability / 10）
        - direction: 方向分（-10 到 +10）
        - sustainability: 持續性分（0-10）
        - news_label: 分類標籤（持續性利好/一日遊利好/...）
        - rerank_reason: LLM 評分理由
    """
    if not candidates:
        return []

    # 候選少於等於 top_k，無需重排
    if len(candidates) <= top_k:
        return candidates[:top_k]

    # 構建 prompt
    prompt = _build_rerank_prompt(query, candidates)

    # 若未指定供應商，用 news_reranker 階段默認（ox-alpha 推理模型）
    if not preferred_provider:
        from app.core.providers import get_default_provider_for_stage

        preferred_provider = get_default_provider_for_stage("news_reranker")

    try:
        from app.core.llm_client import llm_client

        response = await llm_client.analyze(
            prompt=prompt,
            system_prompt=_RERANK_SYSTEM_PROMPT,
            preferred_provider=preferred_provider,
            json_mode=True,
        )

        parsed = _parse_rerank_response(response.text, len(candidates))
        if not parsed:
            logger.warning("[news_reranker] LLM 響應解析失敗，降級為向量搜索原序")
            return candidates[:top_k]

        # 計算綜合分數並排序
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in parsed:
            composite = _composite_score(item["direction"], item["sustainability"])
            scored.append((composite, item))

        # 按綜合分數降序排序
        scored.sort(key=lambda x: x[0], reverse=True)

        # 取 top_k，附加 rerank 元數據
        result: list[dict[str, Any]] = []
        for composite, item in scored[:top_k]:
            news = dict(candidates[item["id"]])
            news["rerank_score"] = composite
            news["direction"] = item["direction"]
            news["sustainability"] = item["sustainability"]
            news["news_label"] = item["label"]
            news["rerank_reason"] = item["reason"]
            news["vector_similarity"] = news.get("similarity", 0)
            # similarity 字段改為綜合分數，下游格式化時直接用
            news["similarity"] = composite
            result.append(news)

        logger.info(
            f"[news_reranker] 雙維度重排序完成: {len(candidates)} 候選 → top {len(result)} "
            f"(provider={response.provider}, {response.duration_ms}ms)"
        )
        return result

    except Exception as e:
        logger.warning(f"[news_reranker] LLM 重排序失敗，降級為向量搜索原序: {e}")
        return candidates[:top_k]


async def search_with_rerank(
    query: str,
    top_k: int = 10,
    channel: str | None = None,
    days_back: int = 7,
    candidate_multiplier: int = 3,
    preferred_provider: str = "",
) -> list[dict[str, Any]]:
    """向量搜索 TopK 初篩 + LLM 雙維度重排序的完整流程。

    Args:
        query: 用戶查詢
        top_k: 最終返回條數
        channel: 頻道過濾
        days_back: 時間過濾
        candidate_multiplier: 初篩倍數（候選數 = top_k * multiplier）
        preferred_provider: 首選 LLM 供應商

    Returns:
        重排序後的新聞列表，每條含 direction/sustainability/news_label/rerank_score
    """
    from app.services import news_store

    # 1. TopK 初篩（擴大召回）
    candidate_k = min(top_k * candidate_multiplier, 50)
    candidates = news_store.search_relevant_news(
        query=query,
        top_k=candidate_k,
        channel=channel,
        days_back=days_back,
    )

    if not candidates:
        return []

    # 2. LLM 雙維度重排序
    reranked = await rerank_news(
        query=query,
        candidates=candidates,
        top_k=top_k,
        preferred_provider=preferred_provider,
    )

    # 3. 持久化評分結果到 MySQL（建立利好/利空池，自我成長）
    if reranked:
        try:
            from app.services import news_store as _ns

            await _ns.save_sentiment_scores(reranked, query_context=query)
        except Exception as e:
            logger.warning(f"[news_reranker] 評分持久化失敗（不影響重排序結果）: {e}")

    return reranked


def format_reranked_news_for_prompt(
    news_list: list[dict[str, Any]],
    max_items: int = 10,
) -> str:
    """將重排序後的新聞格式化為 prompt 文本（含持續性標籤）。

    格式：
    ## 華爾街見聞相關新聞（LLM 雙維度重排序）
    [2026-08-23] [持續性利好] 標題 (方向: +8, 持續性: 9/10)
      摘要...
      理由: 政策落地+執行時間表+資金配套
      來源: https://wallstreetcn.com/articles/xxx
    """
    if not news_list:
        return ""

    lines = ["## 華爾街見聞相關新聞（LLM 雙維度重排序 — 方向 × 持續性）"]

    # 按標籤分組展示，持續性利好優先
    label_order = [
        "持續性利好",
        "弱利好",
        "一日遊利好",
        "中性",
        "弱利空",
        "持續性利空",
        "一日遊利空",
    ]
    grouped: dict[str, list[dict[str, Any]]] = {label: [] for label in label_order}
    for n in news_list[:max_items]:
        label = n.get("news_label", "中性")
        grouped.setdefault(label, []).append(n)

    for label in label_order:
        items = grouped.get(label, [])
        if not items:
            continue
        lines.append(f"\n### {label}（{len(items)} 條）")
        for n in items:
            title = n.get("title", "")
            summary = n.get("summary", "")[:150]
            date = n.get("date", "")[:10]
            url = n.get("url", "")
            direction = n.get("direction", 0)
            sustainability = n.get("sustainability", 0)
            reason = n.get("rerank_reason", "")
            dir_str = f"+{direction}" if direction > 0 else str(direction)
            lines.append(f"[{date}] [{label}] {title} (方向: {dir_str}, 持續性: {sustainability}/10)")
            if summary:
                lines.append(f"  摘要: {summary}")
            if reason:
                lines.append(f"  分析: {reason}")
            if url:
                lines.append(f"  來源: {url}")
            lines.append("")

    lines.append("引用格式：華爾街見聞，[標題]，[日期]，[URL]")
    lines.append("")
    lines.append("注意：優先關注「持續性利好」，警惕「一日遊利好」的追高風險。")
    return "\n".join(lines)
