"""實時金融數據客戶端 — 從公共 API 抓取大盤指數、板塊行情、財經新聞。

數據源:
1. 新浪財經 hq.sinajs.cn — 大盤指數實時行情
2. 騰訊財經 qt.gtimg.cn — 備用指數行情
3. 後端 dashboard API — 數據庫中的股票統計

所有數據源都是公共免費 API，無需 API Key。
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger("agent.market_data")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

# 新浪指數代碼
_INDEX_CODES = {
    "sh000001": "上證指數",
    "sz399001": "深證成指",
    "sz399006": "創業板指",
    "sh000300": "滬深300",
    "sh000016": "上證50",
    "sh000905": "中證500",
}


class MarketDataClient:
    """實時金融數據客戶端 — 從公共免費 API 抓取大盤指數和板塊行情。

    數據源包括新浪財經（指數實時行情）和騰訊財經（板塊漲跌排行），
    同時整合後端 dashboard API 的數據庫統計數據。
    """

    async def get_market_overview(self) -> dict[str, Any]:
        """獲取全市場概覽：大盤指數 + 後端統計。

        Returns:
            {
                "indices": [{"name": "上證指數", "code": "sh000001", "price": 3990.3, "change_pct": 0.19}, ...],
                "db_stats": {...},  # 來自後端 dashboard
                "timestamp": "2026-08-18 22:30:00",
            }
        """
        indices = await self._get_indices_sina()

        # 嘗試從後端獲取 DB 統計
        db_stats = {}
        try:
            from app.services.backend_client import backend_client

            db_stats = await backend_client.get_market_overview()
        except Exception as e:
            logger.warning(f"後端 dashboard 數據獲取失敗: {e}")

        return {
            "indices": indices,
            "db_stats": db_stats,
            "timestamp": _now_str(),
        }

    async def _get_indices_sina(self) -> list[dict[str, Any]]:
        """從新浪財經獲取大盤指數實時行情。

        新浪 API 返回格式為 var hq_str_sh000001="名稱,昨收,今收,...",
        本方法解析每行並計算漲跌幅。

        Returns:
            list[dict]: 指數行情列表，每項含 name / code / price / change_pct；
                        獲取失敗時返回空列表
        """
        codes = ",".join(_INDEX_CODES.keys())
        try:
            async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
                resp = await client.get(f"https://hq.sinajs.cn/list={codes}")
                resp.raise_for_status()
                # 新浪返回 var hq_str_sh000001="上證指數,3979.49,3982.65,3990.30,..."
                lines = resp.text.strip().split("\n")
                indices = []
                for line in lines:
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    code_part = line.split("=")[0].split("_")[-1]
                    data_part = line.split('"')[1] if '"' in line else ""
                    fields = data_part.split(",")
                    if len(fields) < 4:
                        continue
                    name = fields[0]
                    preclose = _safe_float(fields[2])
                    current = _safe_float(fields[3])
                    change_pct = ((current - preclose) / preclose * 100) if preclose else 0
                    indices.append(
                        {
                            "name": name,
                            "code": code_part,
                            "price": current,
                            "preclose": preclose,
                            "change_pct": round(change_pct, 2),
                        }
                    )
                logger.info(f"獲取 {len(indices)} 個指數行情")
                return indices
        except Exception as e:
            logger.warning(f"新浪指數獲取失敗: {e}")
            return []

    async def get_sector_performance(self) -> list[dict[str, Any]]:
        """獲取行業板塊漲跌幅排行（從騰訊財經）。

        Returns:
            [{"sector": "半導體", "change_pct": 3.5, "leader": "xxx"}, ...]
        """
        # 騰訊板塊 API
        try:
            async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
                resp = await client.get(
                    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/rankBK/getBKRank",
                    params={"type": "industry", "sort": "3", "page": "0", "num": "20"},
                )
                resp.raise_for_status()
                data = resp.json()
                sectors = []
                for item in data.get("data", {}).get("rankBK", [])[:20]:
                    sectors.append(
                        {
                            "sector": item.get("name", ""),
                            "change_pct": _safe_float(item.get("changePct", 0)),
                            "leader": item.get("leaderName", ""),
                        }
                    )
                logger.info(f"獲取 {len(sectors)} 個行業板塊")
                return sectors
        except Exception as e:
            logger.warning(f"騰訊板塊數據獲取失敗: {e}")
            return []


def _safe_float(val) -> float:
    """安全轉換為 float，轉換失敗時返回 0.0。

    Args:
        val: 待轉換的值（可能是字符串、數字或 None）

    Returns:
        float: 轉換後的浮點數，失敗時為 0.0
    """
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _now_str() -> str:
    """獲取當前時間的字符串表示（格式 YYYY-MM-DD HH:MM:SS）。

    Returns:
        str: 當前本地時間字符串
    """
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 全局市場數據客戶端單例
market_data_client = MarketDataClient()
