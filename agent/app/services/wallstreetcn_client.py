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
- ⚠️ 請求節流：5 分鐘最小間隔 + 隨機抖動，避免被禁 IP
- ⚠️ 結果緩存：5 分鐘內相同請求返回緩存，不重複請求 API
"""

import asyncio
import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("agent.wallstreetcn")

# ===== 配置 =====
_BASE_URL = "https://api-one-wscn.awtmt.com"
_LIVE_URL = "https://api-one.wallstcn.com"
_TIMEOUT = 15.0
_MAX_RETRIES = 2

# ===== 請求節流配置 =====
# 華爾街見聞 API 請求間隔限制，避免被禁 IP
_MIN_REQUEST_INTERVAL = 300  # 5 分鐘最小間隔（秒）
_JITTER_MAX = 60  # 隨機抖動上限（秒），實際間隔 = 300 + random(0, 60)
_CACHE_TTL = 300  # 緩存有效期（秒），與最小間隔一致

# 頻道映射（wallstreetcn API 頻道代碼 → 中文名）
CHANNEL_MAP = {
    "global": "global-channel",
    "a-stock": "a-stock-channel",
    "us-stock": "us-stock-channel",
    "hk-stock": "hk-stock-channel",
    "forex": "forex-channel",
    "commodity": "commodity-channel",
}


# ===== 全局請求節流器 + 緩存 =====
class _RequestThrottle:
    """全局請求節流器 — 確保 API 請求間隔 ≥ 5 分鐘 + 隨機抖動。

    同時提供結果緩存：5 分鐘內相同請求返回緩存，不重複請求 API。
    """

    def __init__(self):
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()
        self._cache: dict[str, tuple[float, Any]] = {}  # key -> (timestamp, result)
        self._test_mode: bool = False  # 測試模式：禁用節流等待

    def enable_test_mode(self):
        """啟用測試模式 — 禁用節流等待（僅用於測試）。"""
        self._test_mode = True
        self._last_request_time = 0.0
        self._cache.clear()

    def _cache_key(self, endpoint: str, **params) -> str:
        """生成緩存鍵。"""
        sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
        return f"{endpoint}?{sorted_params}"

    def _get_cached(self, key: str) -> Any | None:
        """獲取緩存結果（若未過期）。"""
        if key in self._cache:
            ts, result = self._cache[key]
            if time.time() - ts < _CACHE_TTL:
                logger.debug(f"[wallstreetcn] 緩存命中: {key} (age={int(time.time() - ts)}s)")
                return result
            else:
                del self._cache[key]
        return None

    def _set_cached(self, key: str, result: Any) -> None:
        """存入緩存。"""
        self._cache[key] = (time.time(), result)

    async def throttled_request(
        self,
        endpoint: str,
        fetch_fn,
        **params,
    ) -> Any:
        """節流請求 — 確保全局請求間隔 ≥ 5 分鐘，並緩存結果。

        Args:
            endpoint: 端點標識（用於緩存鍵）
            fetch_fn: 實際抓取函數（async callable）
            **params: 請求參數（用於緩存鍵）

        Returns:
            抓取結果（可能是緩存的）
        """
        cache_key = self._cache_key(endpoint, **params)

        # 1. 檢查緩存
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # 2. 節流等待（全局鎖確保串行）
        async with self._lock:
            # 再次檢查緩存（可能在等待鎖的期間已被其他請求填充）
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            now = time.time()
            elapsed = now - self._last_request_time
            min_interval = _MIN_REQUEST_INTERVAL + random.uniform(0, _JITTER_MAX)

            if not self._test_mode and self._last_request_time > 0 and elapsed < min_interval:
                wait_time = min_interval - elapsed
                logger.info(
                    f"[wallstreetcn] 請求節流: 等待 {wait_time:.0f}s "
                    f"(距上次請求 {elapsed:.0f}s, 最小間隔 {min_interval:.0f}s)"
                )
                await asyncio.sleep(wait_time)

            # 3. 執行請求
            result = await fetch_fn()
            self._last_request_time = time.time()

            # 4. 存入緩存
            self._set_cached(cache_key, result)
            return result

    def get_status(self) -> dict[str, Any]:
        """獲取節流器狀態。"""
        now = time.time()
        elapsed = now - self._last_request_time if self._last_request_time > 0 else 0
        return {
            "last_request_ago_seconds": round(elapsed, 1),
            "min_interval_seconds": _MIN_REQUEST_INTERVAL,
            "jitter_max_seconds": _JITTER_MAX,
            "cache_entries": len(self._cache),
            "cache_ttl_seconds": _CACHE_TTL,
            "next_request_in_seconds": max(0, round(_MIN_REQUEST_INTERVAL - elapsed, 1)) if self._last_request_time > 0 else 0,
        }


# 全局節流器實例
_throttle = _RequestThrottle()

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


async def _fetch_latest_articles_raw(
    channel: str = "global",
    limit: int = 20,
    cursor: str = "",
) -> list[dict[str, Any]]:
    """抓取最新文章的內部實現（不過節流器，供複合函數調用）。"""
    articles, _ = await _fetch_latest_articles_with_cursor(channel, limit, cursor)
    return articles


async def _fetch_latest_articles_with_cursor(
    channel: str = "global",
    limit: int = 20,
    cursor: str = "",
) -> tuple[list[dict[str, Any]], str]:
    """抓取最新文章（帶 cursor 分頁）。

    Returns:
        (articles, next_cursor) — next_cursor 為空表示已到末尾
    """
    limit = min(limit, 50)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            params = {
                "channel": channel,
                "accept": "article",
                "limit": limit,
            }
            if cursor:
                params["cursor"] = cursor
            resp = await client.get(
                f"{_BASE_URL}/apiv1/content/information-flow",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            articles = [
                _normalize_article(item, channel)
                for item in items
                if item.get("resource") and item.get("resource_type") == "article"
            ]
            next_cursor = data.get("data", {}).get("next_cursor", "") or ""
            logger.info(f"[wallstreetcn] 最新文章 ({channel}, cursor={'有' if cursor else '無'}): {len(articles)} 條, next_cursor={'有' if next_cursor else '無'}")
            return articles, next_cursor
    except Exception as e:
        logger.warning(f"[wallstreetcn] 抓取最新文章失敗 ({channel}): {e}")
        return [], ""


async def fetch_latest_articles(
    channel: str = "global",
    limit: int = 20,
    cursor: str = "",
) -> list[dict[str, Any]]:
    """抓取最新文章（支持分頁）。

    ⚠️ 受全局節流保護：5 分鐘內相同請求返回緩存結果。
    複合函數（fetch_a_stock_focused/fetch_all_channels）內部調用 _raw 版本，不走節流器。

    Args:
        channel: 頻道（global/a-stock/us-stock/hk-stock/forex/commodity）
        limit: 抓取條數（最大 50）
        cursor: 分頁游標（從上一頁的 next_cursor 獲取）

    Returns:
        標準化新聞列表
    """
    return await _throttle.throttled_request(
        "latest_articles",
        lambda: _fetch_latest_articles_raw(channel, limit, cursor),
        channel=channel,
        limit=limit,
        cursor=cursor,
    )


async def _fetch_headline_articles_raw(limit: int = 10) -> list[dict[str, Any]]:
    """抓取頭條文章的內部實現（不過節流器）。"""
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


async def fetch_headline_articles(limit: int = 10) -> list[dict[str, Any]]:
    """抓取頭條文章。⚠️ 受全局節流保護。"""
    return await _throttle.throttled_request(
        "headlines",
        lambda: _fetch_headline_articles_raw(limit),
        limit=limit,
    )


async def _fetch_hot_articles_raw(period: str = "all") -> list[dict[str, Any]]:
    """抓取熱文的內部實現（不過節流器）。"""
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


async def fetch_hot_articles(period: str = "all") -> list[dict[str, Any]]:
    """抓取熱文。⚠️ 受全局節流保護。

    Args:
        period: 時間範圍（all/day/week/month）
    """
    return await _throttle.throttled_request(
        "hot",
        lambda: _fetch_hot_articles_raw(period),
        period=period,
    )


async def _search_articles_raw(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    """按關鍵詞搜索文章的內部實現（不過節流器）。"""
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


async def search_articles(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    """按關鍵詞搜索文章。⚠️ 受全局節流保護。

    Args:
        keyword: 搜索關鍵詞（如「半導體」「新能源」「英偉達」）
        limit: 返回條數
    """
    return await _throttle.throttled_request(
        "search",
        lambda: _search_articles_raw(keyword, limit),
        keyword=keyword,
        limit=limit,
    )


async def _fetch_live_news_raw(
    channel: str = "global",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """抓取 7x24 快訊的內部實現（不過節流器）。"""
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


async def fetch_live_news(
    channel: str = "global",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """抓取 7x24 快訊。⚠️ 受全局節流保護。

    Args:
        channel: 頻道（global/a-stock/us-stock/hk-stock/forex/commodity）
        limit: 抓取條數（最大 200）
    """
    return await _throttle.throttled_request(
        "live",
        lambda: _fetch_live_news_raw(channel, limit),
        channel=channel,
        limit=limit,
    )


async def fetch_all_channels(limit_per_channel: int = 30) -> list[dict[str, Any]]:
    """抓取所有頻道的最新文章 + 頭條 + 熱文 + 快訊，合併去重。

    用於定時同步任務，一次抓取多個頻道的最新新聞。
    ⚠️ 整體受全局節流保護：5 分鐘內重複調用返回緩存。
    內部子請求使用 _raw 版本，不走節流器（避免複合函數內部多次等待）。

    Args:
        limit_per_channel: 每個頻道抓取條數

    Returns:
        去重後的新聞列表（按 URI 去重）
    """
    async def _do_fetch() -> list[dict[str, Any]]:
        all_articles: list[dict[str, Any]] = []
        seen_uris: set[str] = set()

        # 1. 抓取各頻道最新文章（使用 _raw 版本，不走節流器）
        for channel in CHANNEL_MAP.keys():
            articles = await _fetch_latest_articles_raw(channel, limit_per_channel)
            for a in articles:
                if a["uri"] and a["uri"] not in seen_uris:
                    seen_uris.add(a["uri"])
                    all_articles.append(a)

        # 2. 抓取頭條
        headlines = await _fetch_headline_articles_raw(limit=20)
        for a in headlines:
            if a["uri"] and a["uri"] not in seen_uris:
                seen_uris.add(a["uri"])
                all_articles.append(a)

        # 3. 抓取熱文
        hot = await _fetch_hot_articles_raw()
        for a in hot:
            if a["uri"] and a["uri"] not in seen_uris:
                seen_uris.add(a["uri"])
                all_articles.append(a)

        # 4. 抓取各頻道 7x24 快訊（大幅增加數據量）
        for channel in CHANNEL_MAP.keys():
            lives = await _fetch_live_news_raw(channel, limit=100)
            for a in lives:
                if a["uri"] and a["uri"] not in seen_uris:
                    seen_uris.add(a["uri"])
                    all_articles.append(a)

        logger.info(f"[wallstreetcn] 全頻道合併去重: {len(all_articles)} 條")
        return all_articles

    return await _throttle.throttled_request(
        "all_channels", _do_fetch, limit_per_channel=limit_per_channel
    )


async def fetch_a_stock_focused(
    limit: int = 50,
    *,
    truncate: bool = True,
) -> list[dict[str, Any]]:
    """抓取 A 股聚焦新聞（最新 + 快訊 + 全球宏觀 + 熱文）。

    用於 AI0 行情新聞階段，提供 A 股市場最相關的新聞。
    ⚠️ 整體受全局節流保護：5 分鐘內重複調用返回緩存。
    內部子請求使用 _raw 版本，不走節流器（避免複合函數內部多次等待）。

    Args:
        limit: 總條數上限
        truncate: 是否截斷到 limit 條。
                  True（默認）= 預覽用，只返回前 limit 條；
                  False = 同步入庫用，返回全部去重後的結果（不丟棄已抓取的新聞）。

    Returns:
        去重後的 A 股相關新聞列表
    """
    async def _do_fetch() -> list[dict[str, Any]]:
        all_articles: list[dict[str, Any]] = []
        seen_uris: set[str] = set()

        # 根據 limit 動態調整內部抓取量（limit 大時抓更多源數據）
        # 內部抓取量 = max(默認值, limit * 倍數)，確保去重後仍有足夠條數
        a_stock_latest_n = max(50, limit)
        a_stock_lives_n = max(200, limit * 4)
        global_latest_n = max(30, limit // 2)
        global_lives_n = max(100, limit * 2)

        # 1. A 股頻道最新文章（使用 _raw 版本，不走節流器）
        articles = await _fetch_latest_articles_raw("a-stock", limit=a_stock_latest_n)
        for a in articles:
            if a["uri"] and a["uri"] not in seen_uris:
                seen_uris.add(a["uri"])
                all_articles.append(a)

        # 2. A 股 7x24 快訊（大量）
        lives = await _fetch_live_news_raw("a-stock", limit=a_stock_lives_n)
        for a in lives:
            if a["uri"] and a["uri"] not in seen_uris:
                seen_uris.add(a["uri"])
                all_articles.append(a)

        # 3. 全球頻道（含 A 股相關宏觀新聞）
        global_articles = await _fetch_latest_articles_raw("global", limit=global_latest_n)
        for a in global_articles:
            if a["uri"] and a["uri"] not in seen_uris:
                seen_uris.add(a["uri"])
                all_articles.append(a)

        # 4. 全球快訊
        global_lives = await _fetch_live_news_raw("global", limit=global_lives_n)
        for a in global_lives:
            if a["uri"] and a["uri"] not in seen_uris:
                seen_uris.add(a["uri"])
                all_articles.append(a)

        # 5. 熱文
        hot = await _fetch_hot_articles_raw()
        for a in hot:
            if a["uri"] and a["uri"] not in seen_uris:
                seen_uris.add(a["uri"])
                all_articles.append(a)

        # 按日期排序（新的在前）
        all_articles.sort(key=lambda x: x.get("date", ""), reverse=True)

        # truncate=True（預覽用）：只返回前 limit 條
        # truncate=False（同步用）：返回全部去重後的結果，不丟棄已抓取的新聞
        if truncate and limit > 0:
            result = all_articles[:limit]
        else:
            result = all_articles
        logger.info(
            f"[wallstreetcn] A股聚焦: 返回 {len(result)} 條"
            f"（總抓取 {len(all_articles)} 條, truncate={truncate}）"
        )
        return result

    return await _throttle.throttled_request(
        "a_stock_focused", _do_fetch, limit=limit
    )


# ===== 補抓漏掉的新聞（cursor 分頁，用於啟動時追回歷史數據）=====

# 補抓時每頁間隔（秒）— 比節流間隔短，因為是一次性操作
_CATCHUP_PAGE_INTERVAL = 12


async def fetch_articles_catchup(
    channel: str = "a-stock",
    max_pages: int = 20,
    existing_uris: set[str] | None = None,
    cutoff_date: str = "",
) -> list[dict[str, Any]]:
    """用 cursor 分頁補抓漏掉的新聞（從最新開始往回翻頁）。

    用於系統啟動時追回停機期間漏掉的新聞。
    ⚠️ 不走全局節流器（補抓需要連續翻頁），但每頁間隔 {interval}s 避免被封。

    Args:
        channel: 頻道（a-stock/global/us-stock/hk-stock/forex/commodity）
        max_pages: 最多翻頁數（每頁 50 條，20 頁 = 1000 條上限）
        existing_uris: 已存在的 URI 集合（遇到已存在的停止翻頁）
        cutoff_date: 截止日期（YYYY-MM-DD），早於此日期的文章不抓

    Returns:
        去重後的新聞列表（新的在前）
    """
    import asyncio

    if existing_uris is None:
        existing_uris = set()

    all_articles: list[dict[str, Any]] = []
    seen_uris: set[str] = set()
    cursor = ""
    pages_fetched = 0
    hit_existing = False

    for page in range(max_pages):
        articles, next_cursor = await _fetch_latest_articles_with_cursor(
            channel, limit=50, cursor=cursor
        )
        pages_fetched += 1

        if not articles:
            logger.info(f"[wallstreetcn] 補抓 {channel} 第 {page+1} 頁: 無文章，停止")
            break

        new_count = 0
        old_count = 0
        for a in articles:
            uri = a.get("uri", "")
            date_str = a.get("date", "")

            # 時間過濾：早於 cutoff_date 的跳過
            if cutoff_date and date_str and date_str[:10] < cutoff_date:
                old_count += 1
                continue

            # 去重
            if uri and uri not in seen_uris and uri not in existing_uris:
                seen_uris.add(uri)
                all_articles.append(a)
                new_count += 1

            # 遇到已存在的 URI → 假設後面都是舊的，停止
            if uri and uri in existing_uris:
                hit_existing = True

        logger.info(
            f"[wallstreetcn] 補抓 {channel} 第 {page+1} 頁: "
            f"{len(articles)} 條, 新增 {new_count}, 過期 {old_count}, "
            f"累計 {len(all_articles)} 條"
        )

        # 如果本頁全部是已存在的或過期的，停止翻頁
        if hit_existing and new_count == 0:
            logger.info(f"[wallstreetcn] 補抓 {channel}: 已追上歷史數據，停止")
            break

        if not next_cursor:
            logger.info(f"[wallstreetcn] 補抓 {channel}: 無更多數據，停止")
            break

        cursor = next_cursor

        # 頁間等待（避免被封 IP）
        if page < max_pages - 1:
            await asyncio.sleep(_CATCHUP_PAGE_INTERVAL)

    # 按日期排序（新的在前）
    all_articles.sort(key=lambda x: x.get("date", ""), reverse=True)
    logger.info(
        f"[wallstreetcn] 補抓完成 {channel}: {pages_fetched} 頁, "
        f"{len(all_articles)} 條新聞"
    )
    return all_articles
