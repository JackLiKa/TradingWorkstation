"""財經新聞噪聲過濾器 — 在入庫前過濾非財經相關新聞。

問題：華爾街見聞 7x24 快訊每次抓 200 條，大部分是短文本噪音（體育、娛樂、社會新聞）。
articles（深度文章）質量較高但仍有少量非財經內容。

策略：
1. 關鍵詞白名單：標題或摘要命中任一關鍵詞才保留
2. 黑名單：標題命中黑名詞直接丟棄（廣告、推廣、非財經）
3. 7x24 快從嚴：必須命中關鍵詞；articles 從寬：深度文章默認保留，只過濾黑名單
4. 最小標題長度：過濾過短無意義的快訊

配置：
- NEWS_FILTER_ENABLED：是否啟用過濾（默認 True）
- NEWS_FILTER_KEYWORDS：自定義關鍵詞白名單（逗號分隔，覆蓋默認）
- NEWS_FILTER_BLACKLIST：自定義黑名單（逗號分隔，追加到默認）
"""

import logging
import re
from typing import Any

from app.core.config import settings

logger = logging.getLogger("agent.news_filter")

# ===== 默認關鍵詞白名單 =====
# 涵蓋：宏觀政策、貨幣政策、市場指標、行業板塊、公司動態、國際財經、商品外匯
_DEFAULT_KEYWORDS = [
    # 宏觀政策
    "央行", "降準", "加息", "降息", "CPI", "PPI", "PMI", "GDP", "通脹", "通縮",
    "美聯儲", "聯儲", "Fed", "利率", "國債", "收益率", "貨幣政策", "財政政策",
    "國常會", "國務院", "發改委", "證監會", "銀保監", "監管", "政策",
    # 市場指標
    "牛市", "熊市", "震盪", "反彈", "回調", "突破", "支撐", "壓力", "放量", "縮量",
    "涨停", "跌停", "漲停", "北向", "南向", "主力", "資金", "淨流入", "淨流出",
    "成交額", "換手率", "兩融", "融資", "融券",
    # 行業板塊
    "半導體", "芯片", "國產芯片", "存儲", "大模型", "AI", "人工智能", "算力",
    "新能源", "光伏", "鋰電", "電動車", "醫藥", "生物", "軍工", "航天",
    "有色", "黃金", "銅", "石油", "煤炭", "鋼鐵", "房地產", "銀行", "保險",
    "券商", "消費", "白酒", "食品", "農業", "紡織", "汽車", "機械",
    # 公司動態
    "增持", "減持", "回購", "分紅", "業績", "財報", "年報", "半年報", "季報",
    "預增", "預減", "虧損", "盈利", "營收", "淨利潤", "併購", "重組", "IPO",
    "上市", "退市", "ST", "停牌", "復牌", "解禁", "減持",
    # 國際財經
    "英偉達", "Nvidia", "蘋果", "特斯拉", "谷歌", "微軟", "美團", "拼多多",
    "騰訊", "阿里", "百度", "京東", "比亞迪", "華為", "中芯國際",
    "納斯達克", "標普", "道瓊", "恒生", "恒指", "日經", "歐股",
    # 商品外匯
    "美元", "人民幣", "歐元", "日元", "匯率", "原油", "布倫特", "WTI",
    "黃金", "白銀", "銅價", "鐵礦石", "天然氣",
    # 事件驅動
    "重磅", "獨家", "突發", "利好", "利空", "利好消息", "利空消息",
    "制裁", "關稅", "貿易", "地緣", "衝突", "談判", "協議",
]

# ===== 默認黑名單 =====
# 命中這些詞的新聞直接丟棄
_DEFAULT_BLACKLIST = [
    "廣告", "推廣", "贊助", "sponsored", "promotion",
    "彩票", "博彩", "賭博",
    "娛樂圈", "明星", "綜藝", "選秀",
    "體育", "足球", "籃球", "NBA", "世界盃",
    "八卦", "緋聞", "離婚", "出軌",
]

# 最小標題長度（字符）— 過短的多為無意義快訊
_MIN_TITLE_LENGTH = 8


def _get_keywords() -> set[str]:
    """獲取關鍵詞白名單（.env 覆蓋 > 默認）。"""
    env_keywords = settings.news_filter_keywords
    if env_keywords:
        keywords = {k.strip() for k in env_keywords.split(",") if k.strip()}
        logger.info(f"[news_filter] 使用 .env 自定義關鍵詞: {len(keywords)} 個")
        return keywords
    return set(_DEFAULT_KEYWORDS)


def _get_blacklist() -> set[str]:
    """獲取黑名單（默認 + .env 追加）。"""
    blacklist = set(_DEFAULT_BLACKLIST)
    env_blacklist = settings.news_filter_blacklist
    if env_blacklist:
        for b in env_blacklist.split(","):
            b = b.strip()
            if b:
                blacklist.add(b)
    return blacklist


def _matches_any(text: str, keywords: set[str]) -> bool:
    """檢查文本是否命中任一關鍵詞。"""
    if not text:
        return False
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False


def filter_news_items(
    items: list[dict[str, Any]],
    source_type: str = "article",
) -> list[dict[str, Any]]:
    """過濾新聞列表 — 保留財經相關，丟棄噪音。

    Args:
        items: 新聞列表（每條含 title, summary, channel 等字段）
        source_type: 來源類型
            - "article": 深度文章 — 只過濾黑名單，不要求命中關鍵詞（質量已較高）
            - "live": 7x24 快訊 — 必須命中關鍵詞白名單才保留（噪音多）
            - "mixed": 混合來源 — articles 寬鬆 + live 嚴格

    Returns:
        過濾後的新聞列表
    """
    if not settings.news_filter_enabled:
        return items

    if not items:
        return items

    keywords = _get_keywords()
    blacklist = _get_blacklist()

    kept: list[dict[str, Any]] = []
    rejected_blacklist = 0
    rejected_no_keyword = 0
    rejected_short_title = 0

    for item in items:
        title = item.get("title", "") or ""
        summary = item.get("summary", "") or ""
        text = f"{title} {summary}"

        # 1. 黑名單過濾（所有來源都適用）
        if _matches_any(title, blacklist):
            rejected_blacklist += 1
            continue

        # 2. 最小標題長度
        if len(title.strip()) < _MIN_TITLE_LENGTH:
            rejected_short_title += 1
            continue

        # 3. 關鍵詞白名單（live 從嚴，article 從寬）
        is_live = source_type == "live" or item.get("channel", "") == "live"
        if is_live:
            # 7x24 快訊：必須命中關鍵詞
            if not _matches_any(text, keywords):
                rejected_no_keyword += 1
                continue
        # article 類型：默認保留（質量已較高），只過濾黑名單

        kept.append(item)

    total_rejected = len(items) - len(kept)
    if total_rejected > 0:
        logger.info(
            f"[news_filter] 過濾 {source_type}: {len(items)} → {len(kept)} 條"
            f"（丟棄 {total_rejected}: 黑名單={rejected_blacklist}, "
            f"無關鍵詞={rejected_no_keyword}, 標題過短={rejected_short_title}）"
        )

    return kept


def filter_mixed_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """過濾混合來源新聞 — 自動識別 article vs live 並分別過濾。

    用於 fetch_all_channels / fetch_a_stock_focused 等複合抓取函數的結果。
    """
    if not settings.news_filter_enabled:
        return items

    # 按來源分組
    articles: list[dict[str, Any]] = []
    lives: list[dict[str, Any]] = []
    for item in items:
        channel = item.get("channel", "") or ""
        # 7x24 快訊的 channel 通常為 "live" 或來自 fetch_live_news
        if channel == "live" or "快訊" in channel or "7x24" in channel:
            lives.append(item)
        else:
            articles.append(item)

    # 分別過濾
    filtered_articles = filter_news_items(articles, source_type="article")
    filtered_lives = filter_news_items(lives, source_type="live")

    return filtered_articles + filtered_lives
