"""當日市場摘要 AI — 按需生成當日市場/新聞凝練摘要，同交易日內所有AI複用。

工作流程：
1. 確定交易日（當天或上一個交易日，考慮週末/假日）
2. 從DB數據 + 工具/MCP源獲取市場信息和新聞
3. 用AI凝練濃縮為標準化摘要
4. 持久化到DB（daily_market_digest表）
5. 同交易日內複用，減少工具調用、提高數據命中率、減小幻覺

摘要區分：
- 事實（來自可信數據源）
- 推導解讀
- 不確定性/缺失數據
- 時間戳/數據新鮮度
- 來源引用
- 交易日和生成時間
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from app.agents.state import DailyDigest
from app.core.llm_client import llm_client

logger = logging.getLogger("agent.daily_digest")

# 交易日判斷：週末（週六=5, 週日=6）不是交易日
# 假日需要從DB最新交易日判斷（若當天 > DB最新交易日，用DB最新交易日）


def _resolve_trade_date(latest_trade_date: str | None = None) -> str:
    """解析當前應使用的交易日。

    規則：
    1. 若今天是週末，回退到最近週五
    2. 若DB最新交易日 < 今天，用DB最新交易日（確保數據可用）
    3. 否則用今天

    Args:
        latest_trade_date: DB最新交易日（YYYY-MM-DD），None時用日曆推算

    Returns:
        str: 交易日 YYYY-MM-DD
    """
    today = datetime.now().date()
    # 週末回退到週五
    if today.weekday() == 5:  # 週六
        today = today - timedelta(days=1)
    elif today.weekday() == 6:  # 週日
        today = today - timedelta(days=2)

    today_str = today.strftime("%Y-%m-%d")

    # 若DB最新交易日存在且早於今天，用DB最新交易日（確保數據可用）
    if latest_trade_date and latest_trade_date < today_str:
        return latest_trade_date

    return today_str


SYSTEM_PROMPT = """你是一個專業的A股市場摘要分析師，擅長將多來源市場數據凝練為標準化摘要。

你的職責：
1. **凝練濃縮**：將分散的市場數據、新聞、行業表現凝練為簡潔摘要
2. **標準化格式**：按固定結構輸出（市場概覽/板塊亮點/新聞摘要/情緒/關鍵事件）
3. **區分事實與推導**：明確標註哪些是數據事實，哪些是推導解讀
4. **保留來源**：引用數據來源（DB/工具/MCP）
5. **標註不確定性**：缺失數據或低置信度推導需明確標註

【數據真實性鐵律】
|- 只能引用上方輸入中提供的數據
|- 禁止編造未在輸入中出現的指數點位、漲跌幅、成交額、行業數據
|- 禁止編造新聞事件或政策動態
|- 缺失數據標註「數據不足」而非編造
|- 推導解讀需標註「推導：」前綴

【規則覆核（每次輸出前必須執行）】
生成最終輸出前，silently 覆核：①數據真實性（引用值是否都在輸入中）②JSON 格式（合法 JSON、無 markdown 標記）③合規（不推薦個股買賣、不預測價格）④數據不足標註（不編造）⑤禁止事項（無廢話、不重複輸入）。任一不滿足則修正後再輸出。"""

PROMPT_TEMPLATE = """請基於以下數據生成當日市場摘要。

## 交易日
{trade_date}

## 實時大盤指數
{indices}

## 數據庫統計
{db_stats}

## 多日市場形態
{regime_text}

## 市場廣度與輪動
{breadth_text}
{rotation_text}

## 多日板塊表現
{sector_text}

## 最新交易日行業聚合
{industry_text}

## 財經新聞（已去重合併）
{news_text}

## 你的任務
凝練濃縮以上數據為標準化摘要，區分事實和推導，保留來源引用。

請嚴格按以下 JSON 格式返回（不要加 markdown 代碼塊標記）:
{{
  "market_overview": "市場概覽：指數表現+漲跌家數+成交額（引用具體數據，標註來源）",
  "sector_highlights": "板塊亮點：強勢行業2-3個+弱勢行業1-2個（引用漲跌幅，標註持續性）",
  "news_digest": "新聞摘要：3-5條關鍵新聞凝練（每條1-2句，標註來源和日期）",
  "sentiment": "市場情緒：偏多/中性/偏空 + 具體理由（引用數據）",
  "key_events": ["關鍵事件1", "關鍵事件2", "關鍵事件3"],
  "data_sources": ["DB", "華爾街見聞", "東方財富"]
}}

注意:
|- JSON 中不要加 ```json 標記
|- market_overview 必須引用具體指數點位和漲跌幅
|- news_digest 每條新聞標註來源（如「[華爾街見聞] ...」）
|- 推導解讀用「推導：」前綴標註
|- 缺失數據標註「數據不足」
|- key_events 是當日最重要的3-5個事件（如政策發布、行業異動等）
|- data_sources 列出實際使用的數據來源"""


async def generate_digest(force: bool = False) -> DailyDigest | None:
    """生成當日市場摘要。

    工作流程：
    1. 解析交易日（考慮週末/假日）
    2. 若已有當日摘要且非強制刷新，直接複用
    3. 從DB+工具獲取市場數據和新聞
    4. 用AI凝練濃縮
    5. 持久化到DB + 快取到state

    Args:
        force: 是否強制重新生成（即使當日已有摘要）

    Returns:
        DailyDigest | None: 摘要對象，失敗時返回 None
    """
    from app.services.backend_client import backend_client
    from app.services.market_data_client import market_data_client
    from app.agents.optimizer import state

    # 1. 解析交易日
    latest_trade_date = await backend_client.get_latest_trade_date()
    trade_date = _resolve_trade_date(latest_trade_date)
    logger.info(f"當日摘要：交易日={trade_date}")

    # 2. 檢查是否已有當日摘要（非強制時複用）
    if not force:
        # 先檢查 state 快取
        if state.current_daily_digest and state.daily_digest_date == trade_date:
            logger.info(f"當日摘要已快取（交易日={trade_date}），直接複用")
            return state.current_daily_digest

        # 再檢查 DB
        existing = await backend_client.load_daily_digest(trade_date)
        if existing:
            digest = DailyDigest.from_dict(existing)
            state.current_daily_digest = digest
            state.daily_digest_date = trade_date
            logger.info(f"當日摘要從DB載入（交易日={trade_date}）")
            return digest

    # 3. 從DB+工具獲取市場數據和新聞
    logger.info(f"生成當日摘要（交易日={trade_date}）...")
    try:
        market_data = await market_data_client.get_market_overview()
    except Exception as e:
        logger.error(f"獲取市場數據失敗: {e}")
        return None

    # 檢查市場數據是否為空 — 若所有數據源都無數據，無法生成有意義的摘要
    indices = market_data.get("indices", [])
    sector_perf = market_data.get("sector_performance", [])
    industry_daily = market_data.get("industry_daily", [])
    news = market_data.get("news", [])
    if not indices and not sector_perf and not industry_daily and not news:
        logger.warning(f"交易日 {trade_date} 無任何市場數據（指數/板塊/行業/新聞均為空），無法生成摘要")
        return None

    # 格式化數據為 prompt 文本
    indices_text = _format_indices(market_data.get("indices", []))
    db_stats = market_data.get("db_stats", {})
    db_stats_text = json.dumps(db_stats, ensure_ascii=False, indent=2, default=str) if db_stats else "無"

    # 市場形態
    regime = market_data.get("regime", {})
    regime_text = _format_regime(regime)

    # 廣度與輪動
    breadth = market_data.get("market_breadth", {})
    rotation = market_data.get("rotation", {})
    breadth_text = _format_breadth(breadth)
    rotation_text = _format_rotation(rotation)

    # 板塊表現
    sector_perf = market_data.get("sector_performance", [])
    sector_text = _format_sector(sector_perf)

    # 行業聚合
    industry_daily = market_data.get("industry_daily", [])
    industry_text = _format_industry(industry_daily)

    # 新聞
    news = market_data.get("news", [])
    news_text = _format_news(news)

    # 4. 用AI凝練濃縮
    prompt = PROMPT_TEMPLATE.format(
        trade_date=trade_date,
        indices=indices_text,
        db_stats=db_stats_text,
        regime_text=regime_text,
        breadth_text=breadth_text,
        rotation_text=rotation_text,
        sector_text=sector_text,
        industry_text=industry_text,
        news_text=news_text,
    )

    try:
        from app.core.providers import get_default_provider_for_stage
        preferred = get_default_provider_for_stage("market_news")
        response = await llm_client.analyze(prompt, SYSTEM_PROMPT, preferred_provider=preferred, json_mode=True)

        if not response.text or not response.text.strip():
            logger.warning("當日摘要AI返回空輸出")
            return None

        # 解析JSON
        cleaned = response.text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)

        # 構建 DailyDigest
        digest = DailyDigest(
            trade_date=trade_date,
            timestamp=datetime.now().isoformat(),
            market_overview=data.get("market_overview", ""),
            sector_highlights=data.get("sector_highlights", ""),
            news_digest=data.get("news_digest", ""),
            sentiment=data.get("sentiment", ""),
            key_events=data.get("key_events", []),
            data_sources=data.get("data_sources", []),
        )

        # 驗證生成結果有實質內容 — market_overview 是必要字段
        if digest.is_empty():
            logger.warning(f"當日摘要AI返回空內容（trade_date={trade_date}, market_overview為空）")
            return None

        # 5. 持久化到DB
        try:
            await backend_client.save_daily_digest(
                trade_date=digest.trade_date,
                market_overview=digest.market_overview,
                sector_highlights=digest.sector_highlights,
                news_digest=digest.news_digest,
                sentiment=digest.sentiment,
                key_events=digest.key_events,
                data_sources=digest.data_sources,
            )
            logger.info(f"當日摘要已持久化到DB（交易日={trade_date}）")
        except Exception as e:
            logger.warning(f"當日摘要持久化失敗（不影響快取）: {e}")

        # 快取到 state
        state.current_daily_digest = digest
        state.daily_digest_date = trade_date

        logger.info(f"當日摘要生成完成（交易日={trade_date}）")
        return digest

    except json.JSONDecodeError as e:
        logger.error(f"當日摘要JSON解析失敗: {e}")
        return None
    except Exception as e:
        logger.error(f"當日摘要生成異常: {e}", exc_info=True)
        return None


def _format_indices(indices: list[dict]) -> str:
    """格式化指數數據。"""
    if not indices:
        return "實時數據獲取失敗"
    lines = []
    for idx in indices:
        name = idx.get("name", "")
        code = idx.get("code", "")
        price = idx.get("price", 0)
        change = idx.get("change_pct", 0)
        arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
        lines.append(f"  {name}({code}): {price} {arrow} {change}%")
    return "\n".join(lines)


def _format_regime(regime: dict) -> str:
    """格式化市場形態。"""
    if not regime or regime.get("regime_type") == "unknown":
        return "數據不足，無法計算市場形態"
    lines = [f"形態類型: {regime.get('regime_type', 'unknown')}"]
    desc = regime.get("description", "")
    if desc:
        lines.append(f"描述: {desc}")
    metrics = regime.get("metrics", {})
    if metrics:
        lines.append(f"累計漲跌幅: {metrics.get('total_change', 0)}%")
        lines.append(f"波動率: {metrics.get('volatility', 0)}%")
        lines.append(f"交替次數: {metrics.get('alternations', 0)}")
    return "\n".join(lines)


def _format_breadth(breadth: dict) -> str:
    """格式化市場廣度。"""
    if not breadth or not breadth.get("summary"):
        return "無市場廣度數據"
    return f"摘要: {breadth.get('summary', '')}"


def _format_rotation(rotation: dict) -> str:
    """格式化輪動信號。"""
    if not rotation or not rotation.get("summary"):
        return "無輪動信號數據"
    lines = [f"摘要: {rotation.get('summary', '')}"]
    leading = rotation.get("leadingIndustries", [])
    if leading:
        lines.append("領漲: " + ", ".join([f"{i.get('name', '')}({i.get('change', 0):+.2f}%)" for i in leading[:3]]))
    return "\n".join(lines)


def _format_sector(sector_perf: list[dict]) -> str:
    """格式化板塊表現。"""
    if not sector_perf:
        return "無板塊表現數據"
    # 按日期分組，取最新交易日
    by_date: dict[str, list[dict]] = {}
    for row in sector_perf:
        date = str(row.get("date", ""))
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(row)

    if not by_date:
        return "無板塊表現數據"

    latest_date = max(by_date.keys())
    sectors = sorted(by_date[latest_date], key=lambda x: x.get("avgPctChange", 0) or 0, reverse=True)
    lines = [f"=== {latest_date} ==="]
    lines.append("強勢: " + ", ".join([f"{s.get('industry', '')}({s.get('avgPctChange', 0):+.2f}%)" for s in sectors[:3]]))
    if len(sectors) > 3:
        lines.append("弱勢: " + ", ".join([f"{s.get('industry', '')}({s.get('avgPctChange', 0):+.2f}%)" for s in sectors[-3:]]))
    return "\n".join(lines)


def _format_industry(industry_daily: list[dict]) -> str:
    """格式化行業聚合。"""
    if not industry_daily:
        return "無行業聚合數據"
    lines = [f"交易日: {industry_daily[0].get('tradeDate', '')}"]
    for item in industry_daily[:10]:
        industry = item.get("industry", "")
        avg = item.get("avgPctChg")
        rising = item.get("risingCount", 0)
        falling = item.get("fallingCount", 0)
        avg_str = f"{avg:.2f}%" if avg is not None else "N/A"
        lines.append(f"  {industry}: {avg_str} (漲{rising}/跌{falling})")
    return "\n".join(lines)


def _format_news(news: list[dict]) -> str:
    """格式化新聞。"""
    if not news:
        return "無新聞數據"
    lines = []
    for n in news[:10]:
        title = n.get("title", "")
        source = n.get("source", "")
        date = n.get("date", "")
        lines.append(f"  [{date}] {title} ({source})")
    return "\n".join(lines)
