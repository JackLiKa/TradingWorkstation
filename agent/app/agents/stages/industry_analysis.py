"""AI 0.5: 行業分析 — 根據行情新聞 + 數據庫行業數據篩選股票。

根據行情新聞 AI 的行業情緒總結，結合數據庫中的 stock_industry 表，
篩選出利好行業的股票代碼，縮小選股範圍。

輸入: 行情新聞分析結果、數據庫行業數據
輸出: JSON { reasoning, favorable_industries, filtered_codes }
範式: JSON，包含利好行業列表和篩選後的股票代碼
"""
import json
import logging
from typing import Any

from app.agents.stages.base import BaseStage
from app.services.backend_client import backend_client

logger = logging.getLogger("agent.stage.industry")

SYSTEM_PROMPT = """你是一個專業的 A 股行業分析師，擅長將實時行情新聞與數據庫行業分類結合，
精準識別利好行業並篩選對應股票。

你需要：
1. 從行情新聞中提取利好行業關鍵詞
2. 將關鍵詞與數據庫中的行業分類匹配（支持模糊匹配）
3. 輸出利好行業列表和對應的股票代碼

注意：行業分類可能很細（如 "J66證券期貨業"、"G56鐵路運輸業"），
你需要能將新聞中的 "證券" 匹配到 "J66證券期貨業"。"""

PROMPT_TEMPLATE = """請根據行情新聞分析結果，結合數據庫行業數據，篩選利好行業的股票。

## 行情新聞分析
{market_news}

## 數據庫中的行業列表
{industry_list}

## 行業下的股票代碼（抽樣）
{industry_stocks}

## 你的任務
1. 從行情新聞中識別利好行業關鍵詞
2. 將關鍵詞與數據庫行業分類匹配
3. 列出利好行業和對應的股票代碼

請嚴格按以下 JSON 格式返回:
```json
{{
  "reasoning": "分析理由（1-2句話）",
  "favorable_industries": ["行業1", "行業2"],
  "filtered_codes": ["sh.600000", "sz.000001"]
}}
```

注意:
- filtered_codes 最多 50 個
- 如果無法匹配到利好行業，返回空列表
- 行業名稱用數據庫中的完整名稱"""


class IndustryAnalysisStage(BaseStage):
    """AI 0.5: 行業分析節點 — 行業篩選。"""

    def __init__(self):
        super().__init__(stage_name="industry_analysis", display_name="AI 0.5 · 行業分析")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行行業分析。

        kwargs:
            market_news: str — 行情新聞分析結果
        """
        market_news = kwargs.get("market_news", "")

        # === 從後端獲取行業列表 ===
        logger.info("[AI0.5] 獲取數據庫行業數據...")
        industry_list = await backend_client.get_industry_list()

        # === 抽樣：每個行業取幾個股票代碼 ===
        industry_stocks = {}
        for industry in industry_list[:30]:  # 限制前30個行業避免 token 過多
            try:
                stocks = await backend_client.get_industries(industry=industry)
                codes = [s.get("code", "") for s in stocks[:5]]  # 每個行業取5個
                if codes:
                    industry_stocks[industry] = codes
            except Exception:
                continue

        prompt = PROMPT_TEMPLATE.format(
            market_news=market_news[:2000],  # 截斷避免 token 過多
            industry_list=json.dumps(industry_list[:50], ensure_ascii=False, indent=2),
            industry_stocks=json.dumps(industry_stocks, ensure_ascii=False, indent=2),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt)
        logger.info(f"[AI0.5 行業分析] {response[:100]}...")
        return response


def parse_industry_output(response: str) -> dict[str, Any]:
    """解析行業分析 AI 的 JSON 輸出。"""
    json_start = response.find("```json")
    if json_start >= 0:
        json_start = response.find("{", json_start)
        json_end = response.rfind("}")
        if json_start >= 0 and json_end > json_start:
            return json.loads(response[json_start:json_end + 1])

    brace_start = response.find("{")
    brace_end = response.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        return json.loads(response[brace_start:brace_end + 1])

    raise ValueError(f"無法從行業分析 AI 響應中提取 JSON: {response[:200]}")
