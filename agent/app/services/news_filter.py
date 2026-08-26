"""財經新聞噪聲過濾器 — 關鍵詞權重評分 + 標籤優先級 + 黑名單。

問題：華爾街見聞 7x24 快訊每次抓 200 條，大部分是短文本噪音（體育、娛樂、社會新聞）。
articles（深度文章）質量較高但仍有少量非財經內容。

策略（三層過濾）：
1. 黑名單一票否決：標題命中黑名單詞直接丟棄（廣告、娛樂、體育等）
2. 關鍵詞權重評分：標題+摘要命中關鍵詞累加權重分數，達到閾值才保留
   - 高權重詞（央行/降準/加息/CPI/美聯儲）= 3 分
   - 中權重詞（半導體/芯片/增持/業績/財報）= 2 分
   - 低權重詞（反彈/回調/震盪/放量）= 1 分
3. 標籤優先級：帶有「獨家」「宏觀」「重磅」「深度」標籤的文章加分

來源類型差異：
- article（深度文章）：閾值低（1 分），質量已較高
- live（7x24 快訊）：閾值高（2 分），噪音多需嚴格過濾

配置：
- NEWS_FILTER_ENABLED：是否啟用過濾（默認 True）
- NEWS_FILTER_KEYWORDS：自定義關鍵詞白名單（逗號分隔，覆蓋默認）
- NEWS_FILTER_BLACKLIST：自定義黑名單（逗號分隔，追加到默認）
- NEWS_FILTER_SCORE_THRESHOLD_LIVE：快訊評分閾值（默認 2）
- NEWS_FILTER_SCORE_THRESHOLD_ARTICLE：文章評分閾值（默認 1）
"""

import logging
import re
from typing import Any

from app.core.config import settings

logger = logging.getLogger("agent.news_filter")

# ===== 關鍵詞權重分級 =====
# 高權重（3 分）：宏觀政策核心詞，命中即高度相關
_HIGH_WEIGHT_KEYWORDS = [
    # 宏觀政策核心
    "央行", "降準", "加息", "降息", "CPI", "PPI", "PMI", "GDP", "通脹", "通縮",
    "美聯儲", "聯儲", "Fed", "利率", "國債", "收益率", "貨幣政策", "財政政策",
    "國常會", "國務院", "發改委", "證監會", "銀保監", "監管",
    # 重大事件
    "重磅", "獨家", "突發", "制裁", "關稅", "貿易戰",
    # 核心公司
    "英偉達", "Nvidia", "蘋果", "特斯拉", "華為", "中芯國際",
]

# 中權重（2 分）：行業板塊 + 公司動態，財經相關性強
_MEDIUM_WEIGHT_KEYWORDS = [
    # 行業板塊
    "半導體", "芯片", "國產芯片", "存儲", "大模型", "AI", "人工智能", "算力",
    "新能源", "光伏", "鋰電", "電動車", "醫藥", "生物", "軍工", "航天",
    "有色", "黃金", "銅", "石油", "煤炭", "鋼鐵", "房地產", "銀行", "保險",
    "券商", "消費", "白酒", "食品", "農業", "汽車", "機械",
    # 公司動態
    "增持", "減持", "回購", "分紅", "業績", "財報", "年報", "半年報", "季報",
    "預增", "預減", "虧損", "盈利", "營收", "淨利潤", "併購", "重組", "IPO",
    "上市", "退市", "ST", "停牌", "復牌", "解禁",
    # 國際財經
    "納斯達克", "標普", "道瓊", "恒生", "恒指", "日經", "歐股",
    "騰訊", "阿里", "百度", "京東", "比亞迪", "美團", "拼多多",
    # 商品外匯
    "美元", "人民幣", "歐元", "日元", "匯率", "原油", "布倫特", "WTI",
    "白銀", "銅價", "鐵礦石", "天然氣",
    # 事件驅動
    "利好", "利空", "地緣", "衝突", "談判", "協議",
]

# 低權重（1 分）：市場現象詞，單獨出現相關性較弱
_LOW_WEIGHT_KEYWORDS = [
    "牛市", "熊市", "震盪", "反彈", "回調", "突破", "支撐", "壓力", "放量", "縮量",
    "涨停", "跌停", "漲停", "北向", "南向", "主力", "資金", "淨流入", "淨流出",
    "成交額", "換手率", "兩融", "融資", "融券",
    "利好消息", "利空消息",
]

# ===== 標籤優先級 =====
# 帶有這些標籤/關鍵詞的文章額外加分（標題中出現）
_PRIORITY_TAGS = ["獨家", "宏觀", "重磅", "深度", "頭條", "焦點", "獨家報導", "獨家專訪"]

# ===== 黑名單 =====
# 命中這些詞的新聞直接丟棄（一票否決）
_DEFAULT_BLACKLIST = [
    "廣告", "推廣", "贊助", "sponsored", "promotion",
    "彩票", "博彩", "賭博",
    "娛樂圈", "明星", "綜藝", "選秀",
    "體育", "足球", "籃球", "NBA", "世界盃",
    "八卦", "緋聞", "離婚", "出軌",
]

# 最小標題長度（字符）— 過短的多為無意義快訊
_MIN_TITLE_LENGTH = 8

# 默認評分閾值
_DEFAULT_THRESHOLD_LIVE = 2  # 快訊：至少 2 分（命中 1 個高權重詞 或 2 個低權重詞）
_DEFAULT_THRESHOLD_ARTICLE = 1  # 文章：至少 1 分（寬鬆，質量已較高）
_TAG_BONUS = 2  # 標籤加分


def _get_keywords() -> dict[str, int]:
    """獲取關鍵詞權重映射（.env 覆蓋 > 默認）。

    Returns:
        dict: {關鍵詞: 權重分數}
    """
    env_keywords = settings.news_filter_keywords
    if env_keywords:
        # .env 自定義關鍵詞：全部按中權重（2 分）處理
        keywords = {k.strip(): 2 for k in env_keywords.split(",") if k.strip()}
        logger.info(f"[news_filter] 使用 .env 自定義關鍵詞: {len(keywords)} 個（均 2 分）")
        return keywords

    # 合併三級權重
    keywords: dict[str, int] = {}
    for kw in _HIGH_WEIGHT_KEYWORDS:
        keywords[kw] = 3
    for kw in _MEDIUM_WEIGHT_KEYWORDS:
        if kw not in keywords:  # 高權重優先
            keywords[kw] = 2
    for kw in _LOW_WEIGHT_KEYWORDS:
        if kw not in keywords:  # 高/中權重優先
            keywords[kw] = 1
    return keywords


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


def _get_threshold_live() -> int:
    """獲取快訊評分閾值。"""
    return getattr(settings, "news_filter_score_threshold_live", _DEFAULT_THRESHOLD_LIVE)


def _get_threshold_article() -> int:
    """獲取文章評分閾值。"""
    return getattr(settings, "news_filter_score_threshold_article", _DEFAULT_THRESHOLD_ARTICLE)


def _compute_score(text: str, keywords: dict[str, int]) -> tuple[int, list[str]]:
    """計算文本的關鍵詞評分。

    Args:
        text: 標題 + 摘要文本
        keywords: {關鍵詞: 權重} 映射

    Returns:
        (總分, 命中的關鍵詞列表)
    """
    if not text:
        return 0, []
    text_lower = text.lower()
    score = 0
    hit_keywords: list[str] = []
    for kw, weight in keywords.items():
        if kw.lower() in text_lower:
            score += weight
            hit_keywords.append(kw)
    return score, hit_keywords


def _compute_tag_bonus(title: str) -> int:
    """計算標籤優先級加分。

    標題中包含「獨家」「宏觀」「重磅」等標籤詞時額外加分。
    """
    if not title:
        return 0
    bonus = 0
    for tag in _PRIORITY_TAGS:
        if tag in title:
            bonus += _TAG_BONUS
            break  # 只加一次，避免重複
    return bonus


def _matches_any(text: str, keywords: set[str]) -> bool:
    """檢查文本是否命中任一關鍵詞（黑名單用）。"""
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
    """過濾新聞列表 — 關鍵詞權重評分 + 標籤優先級 + 黑名單。

    Args:
        items: 新聞列表（每條含 title, summary, channel 等字段）
        source_type: 來源類型
            - "article": 深度文章 — 閾值低（1 分），質量已較高
            - "live": 7x24 快訊 — 閾值高（2 分），噪音多需嚴格過濾
            - "mixed": 混合來源 — articles 寬鬆 + live 嚴格

    Returns:
        過濾後的新聞列表（保留的項會增加 _filter_score 字段供調試）
    """
    if not settings.news_filter_enabled:
        return items

    if not items:
        return items

    keywords = _get_keywords()
    blacklist = _get_blacklist()
    threshold = _get_threshold_live() if source_type == "live" else _get_threshold_article()

    kept: list[dict[str, Any]] = []
    rejected_blacklist = 0
    rejected_low_score = 0
    rejected_short_title = 0

    for item in items:
        title = item.get("title", "") or ""
        summary = item.get("summary", "") or ""
        text = f"{title} {summary}"

        # 1. 黑名單一票否決（所有來源都適用）
        if _matches_any(title, blacklist):
            rejected_blacklist += 1
            continue

        # 2. 最小標題長度
        if len(title.strip()) < _MIN_TITLE_LENGTH:
            rejected_short_title += 1
            continue

        # 3. 關鍵詞權重評分
        score, hit_kws = _compute_score(text, keywords)

        # 4. 標籤優先級加分
        tag_bonus = _compute_tag_bonus(title)
        total_score = score + tag_bonus

        # 5. 達到閾值才保留
        is_live = source_type == "live" or item.get("channel", "") == "live"
        actual_threshold = _get_threshold_live() if is_live else _get_threshold_article()

        if total_score < actual_threshold:
            rejected_low_score += 1
            continue

        # 保留，附帶評分信息（供調試/排序用）
        item["_filter_score"] = total_score
        item["_filter_hits"] = hit_kws
        kept.append(item)

    total_rejected = len(items) - len(kept)
    if total_rejected > 0:
        logger.info(
            f"[news_filter] 過濾 {source_type}: {len(items)} → {len(kept)} 條"
            f"（丟棄 {total_rejected}: 黑名單={rejected_blacklist}, "
            f"低分={rejected_low_score}, 標題過短={rejected_short_title}）"
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


def score_news_item(item: dict[str, Any]) -> int:
    """計算單條新聞的財經相關性評分（供外部排序用）。

    Args:
        item: 新聞 dict（含 title, summary）

    Returns:
        評分（越高越相關）
    """
    title = item.get("title", "") or ""
    summary = item.get("summary", "") or ""
    text = f"{title} {summary}"
    keywords = _get_keywords()
    score, _ = _compute_score(text, keywords)
    tag_bonus = _compute_tag_bonus(title)
    return score + tag_bonus
