"""華爾街見聞新聞抓取客戶端 — 合法接入公開 API。

數據來源：華爾街見聞 (wallstreetcn.com) 公開 API
- llms.txt 明確允許 AI 搜索、實時引用、問答摘要（須注明來源）
- 禁止：無歸屬的商業模型訓練
- 引用格式：華爾街見聞，[標題]，[YYYY-MM-DD]，https://wallstreetcn.com/articles/[id]

API 端點（無需 API Key）：
- 最新文章: https://api-one-wscn.awtmt.com/apiv1/content/information-flow?channel=global&accept=article&limit=10
- 頭條文章: https://api-one-wscn.awtmt.com/apiv1/content/carousel/information-flow?channel=global&limit=10
- 熱文:     https://api-one-wscn.awtmt.com/apiv1/content/articles/hot?period=all
- 搜索:     https://api-one-wscn.awtmt.com/apiv1/search/article?query=关键词&limit=10
- 7x24快訊: https://api-one.wallstcn.com/apiv1/content/lives?channel={channel}&limit=200

頻道（channel）：
- global-channel（全球）、a-stock-channel（A股）、us-stock-channel（美股）
- forex-channel（外汇）、commodity-channel（商品）、hk-stock-channel（港股）

設計要點：
- 自動降級：API 不可用時返回空列表，不影響優化循環
- URI 去重：基於文章 URI 去重，避免重複入庫
- 數據清洗：去除 HTML 標籤、規範化日期、提取摘要
- 來源標注：所有新聞標注來源為「華爾街見聞」
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("agent.wallstreetcn")

# ===== 配置 =====
_BASE_URL = "https://api-one-wscn.awtmt.com"
_LIVE_URL = "https://api-one.wallstcn.com"
_TIMEOUT = 15.0
_MAX_RETRIES = 2

# 頻道映射（wallstreetcn API 頻道代碼 → 中文名）
CHANNEL_MAP = {
    "global": "global-channel",
    "a-stock": "a-stock-channel",
    "us-stock": "us-stock-channel",
    "hk-stock": "hk-stock-channel",
    "forex": "forex-channel",
    "commodity": "commodity-channel",
}

# 請求頭（模擬正常瀏覽器，遵守 robots.txt）
_HEADERS = {
    "User-Agent": "TradingWorkstation/1.0 (research; contact: dev@local)",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://wallstreetcn.com/",
}


def _clean_html(text: str) -> str:
    """去除 HTML 標籤，保留純文本。"""
    if not text:
        return ""
    # 去除 <p>、<br> 等標籤
    text = re.sub(r"<[^>]+>", "", text)
    # 去除 HTML 實體
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # 壓縮空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_timestamp(ts: Any) -> str:
    """將時間戳（秒或毫秒）轉為 ISO 日期字符串 (YYYY-MM-DD)。"""
    if not ts:
        return ""
    try:
        ts_int = int(ts)
        # 華爾街見聞用秒級時間戳
        if ts_int > 1e12:  # 毫秒級
            ts_int = ts_int // 1000
        dt = datetime.fromtimestamp(ts_int, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return ""


def _normalize_article(item: dict[str, Any], channel: str = "global") -> dict[str, Any]:
    """將華爾街見聞 API 返回的文章標準化為統一新聞格式。

    返回格式：
    {
        "uri": "文章唯一標識（用於去重）",
        "title": "標題",
        "summary": "摘要（已清洗 HTML）",
        "content": "正文摘要（已清洗）",
        "source": "華爾街見聞",
        "author": "作者名",
        "date": "YYYY-MM-DD HH:MM:SS",
        "url": "完整 URL",
        "channel": "頻道",
        "image_url": "配圖 URL（可選）",
    }
    """
    resource = item.get("resource", item)  # information-flow 嵌套在 resource 中
    uri = resource.get("uri", "") or resource.get("id", "")
    title = resource.get("title", "") or ""
    # 摘要：優先 content_short，其次 summary
    summary = _clean_html(resource.get("content_short", "") or resource.get("summary", "") or "")
    # 正文：若 有 content，取前 500 字作為正文摘要
    content = _clean_html(resource.get("content", "") or "")[:500]
    if not summary and content:
        summary = content[:200]
    author = resource.get("author", {})
    if isinstance(author, dict):
        author_name = author.get("display_name", "")
    else:
        author_name = str(author)
    date = _parse_timestamp(resource.get("display_time", 0))
    # API 返回的 uri 字段已是完整 URL（如 https://wallstreetcn.com/articles/3780065）
    # uri_short 是短鏈接，url 是備選
    url = resource.get("uri_short", "") or resource.get("url", "") or ""
    # 若 uri 本身就是完整 URL，直接用作 url
    raw_uri = resource.get("uri", "") or ""
    if raw_uri.startswith("http") and not url:
        url = raw_uri
    # 若 url 仍為空且 uri 是純 ID，拼接前綴
    if not url and raw_uri and not raw_uri.startswith("http"):
        url = f"https://wallstreetcn.com/articles/{raw_uri}"
    # uri 用作唯一標識：若 uri 是完整 URL，取最後一段作為 ID
    if raw_uri.startswith("http"):
        uri = raw_uri.rstrip("/").split("/")[-1]
    else:
        uri = str(raw_uri) or str(resource.get("id", ""))
    image_url = resource.get("image", "")
    if isinstance(image_url, dict):
        image_url = image_url.get("uri", "")

    return {
        "uri": str(uri),
        "title": title.strip(),
        "summary": summary,
        "content": content,
        "source": "華爾街見聞",
        "author": author_name,
        "date": date,
        "url": url,
        "channel": channel,
        "image_url": image_url,
    }


def _normalize_live(item: dict[str, Any], channel: str = "global") -> dict[str, Any]:
    """將 7x24 快訊 API 返回的條目標準化。"""
    uri = str(item.get("id", ""))
    title = item.get("title", "") or ""
    content_text = _clean_html(item.get("content_text", "") or item.get("content", "") or "")
    date = _parse_timestamp(item.get("display_time", 0))
    url = item.get("uri", "") or f"https://wallstreetcn.com/live/{uri}"

    return {
        "uri": uri,
        "title": title.strip() if title else content_text[:60],
        "summary": content_text[:200],
        "content": content_text[:500],
        "source": "華爾街見聞",
        "author": "7x24快訊",
        "date": date,
        "url": url,
        "channel": channel,
        "image_url": "",
    }


async def fetch_latest_articles(
    channel: str = "global",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """抓取最新文章。

    Args:
        channel: 頻道（global/a-stock/us-stock/hk-stock/forex/commodity）
        limit: 抓取條數（最大 50）

    Returns:
        標準化新聞列表
    """
    limit = min(limit, 50)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                f"{_BASE_URL}/apiv1/content/information-flow",
                params={
                    "channel": channel,
                    "accept": "article",
                    "limit": limit,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            # 只取 resource_type == "article" 的條目，過濾廣告/banner
            articles = [
                _normalize_article(item, channel)
                for item in items
                if item.get("resource") and item.get("resource_type") == "article"
            ]
            logger.info(f"[wallstreetcn] 最新文章 ({channel}): {len(articles)} 條")
            return articles
    except Exception as e:
        logger.warning(f"[wallstreetcn] 抓取最新文章失敗 ({channel}): {e}")
        return []


async def fetch_headline_articles(limit: int = 10) -> list[dict[str, Any]]:
    """抓取頭條文章。"""
    limit = min(limit, 20)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                f"{_BASE_URL}/apiv1/content/carousel/information-flow",
                params={"channel": "global", "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            articles = [
                _normalize_article(item, "headline")
                for item in items
                if item.get("resource") and item.get("resource_type") == "article"
            ]
            logger.info(f"[wallstreetcn] 頭條文章: {len(articles)} 條")
            return articles
    except Exception as e:
        logger.warning(f"[wallstreetcn] 抓取頭條文章失敗: {e}")
        return []


async def fetch_hot_articles(period: str = "all") -> list[dict[str, Any]]:
    """抓取熱文。

    Args:
        period: 時間範圍（all/day/week/month）
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                f"{_BASE_URL}/apiv1/content/articles/hot",
                params={"period": period},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            articles = [
                _normalize_article(item, "hot")
                for item in items
                if item.get("resource") and item.get("resource_type") == "article"
            ]
            logger.info(f"[wallstreetcn] 熱文 ({period}): {len(articles)} 條")
            return articles
    except Exception as e:
        logger.warning(f"[wallstreetcn] 抓取熱文失敗: {e}")
        return []


async def search_articles(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    """按關鍵詞搜索文章。

    Args:
        keyword: 搜索關鍵詞（如「半導體」「新能源」「英偉達」）
        limit: 返回條數
    """
    limit = min(limit, 20)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                f"{_BASE_URL}/apiv1/search/article",
                params={"query": keyword, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            articles = [
                _normalize_article(item, "search")
                for item in items
                if item.get("resource") and item.get("resource_type") == "article"
            ]
            logger.info(f"[wallstreetcn] 搜索「{keyword}」: {len(articles)} 條")
            return articles
    except Exception as e:
        logger.warning(f"[wallstreetcn] 搜索「{keyword}」失敗: {e}")
        return []


async def fetch_live_news(
    channel: str = "global",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """抓取 7x24 快訊。

    Args:
        channel: 頻道（global/a-stock/us-stock/hk-stock/forex/commodity）
        limit: 抓取條數（最大 200）
    """
    channel_code = CHANNEL_MAP.get(channel, "global-channel")
    limit = min(limit, 200)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                f"{_LIVE_URL}/apiv1/content/lives",
                params={"channel": channel_code, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            lives = [_normalize_live(item, channel) for item in items]
            logger.info(f"[wallstreetcn] 7x24快訊 ({channel}): {len(lives)} 條")
            return lives
    except Exception as e:
        logger.warning(f"[wallstreetcn] 抓取7x24快訊失敗 ({channel}): {e}")
        return []


async def fetch_all_channels(limit_per_channel: int = 10) -> list[dict[str, Any]]:
    """抓取所有頻道的最新文章 + 頭條 + 熱文，合併去重。

    用於定時同步任務，一次抓取多個頻道的最新新聞。

    Args:
        limit_per_channel: 每個頻道抓取條數

    Returns:
        去重後的新聞列表（按 URI 去重）
    """
    all_articles: list[dict[str, Any]] = []
    seen_uris: set[str] = set()

    # 1. 抓取各頻道最新文章
    for channel in CHANNEL_MAP.keys():
        articles = await fetch_latest_articles(channel, limit_per_channel)
        for a in articles:
            if a["uri"] and a["uri"] not in seen_uris:
                seen_uris.add(a["uri"])
                all_articles.append(a)

    # 2. 抓取頭條
    headlines = await fetch_headline_articles(limit=10)
    for a in headlines:
        if a["uri"] and a["uri"] not in seen_uris:
            seen_uris.add(a["uri"])
            all_articles.append(a)

    # 3. 抓取熱文
    hot = await fetch_hot_articles()
    for a in hot:
        if a["uri"] and a["uri"] not in seen_uris:
            seen_uris.add(a["uri"])
            all_articles.append(a)

    logger.info(f"[wallstreetcn] 全頻道合併去重: {len(all_articles)} 條")
    return all_articles


async def fetch_a_stock_focused(limit: int = 20) -> list[dict[str, Any]]:
    """抓取 A 股聚焦新聞（最新 + 快訊 + 搜索關鍵詞）。

    用於 AI0 行情新聞階段，提供 A 股市場最相關的新聞。

    Args:
        limit: 總條數上限

    Returns:
        去重後的 A 股相關新聞列表
    """
    all_articles: list[dict[str, Any]] = []
    seen_uris: set[str] = set()

    # 1. A 股頻道最新文章
    articles = await fetch_latest_articles("a-stock", limit=limit // 2)
    for a in articles:
        if a["uri"] and a["uri"] not in seen_uris:
            seen_uris.add(a["uri"])
            all_articles.append(a)

    # 2. A 股 7x24 快訊
    lives = await fetch_live_news("a-stock", limit=limit // 2)
    for a in lives:
        if a["uri"] and a["uri"] not in seen_uris:
            seen_uris.add(a["uri"])
            all_articles.append(a)

    # 3. 全球頻道（可能含 A 股相關宏觀新聞）
    global_articles = await fetch_latest_articles("global", limit=5)
    for a in global_articles:
        if a["uri"] and a["uri"] not in seen_uris:
            seen_uris.add(a["uri"])
            all_articles.append(a)

    # 按日期排序（新的在前）
    all_articles.sort(key=lambda x: x.get("date", ""), reverse=True)

    result = all_articles[:limit]
    logger.info(f"[wallstreetcn] A股聚焦: {len(result)} 條")
    return result
