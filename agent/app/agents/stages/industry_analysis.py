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

from app.agents.few_shot import get_few_shot
from app.agents.stages.base import BaseStage
from app.services.backend_client import backend_client
from app.services.market_data_client import market_data_client

logger = logging.getLogger("agent.stage.industry")

SYSTEM_PROMPT = """你是一個專業的 A 股行業分析師，擅長將實時行情新聞與數據庫行業分類結合，
精準識別利好行業並篩選對應股票。

你需要：
1. 從行情新聞中提取利好行業關鍵詞
2. 結合「最新交易日行業強弱」數據，優先關注新聞提到且當日確實走強的行業
3. 將關鍵詞與數據庫中的行業分類匹配（支持模糊匹配）
4. 輸出利好行業列表和對應的股票代碼

注意：行業分類可能很細（如 "J66證券期貨業"、"G56鐵路運輸業"），
你需要能將新聞中的 "證券" 匹配到 "J66證券期貨業"。

【數據真實性鐵律】
- favorable_industries 中的行業名稱必須來自上方「數據庫中的行業列表」，禁止編造不存在的行業分類
- filtered_codes 中的股票代碼必須來自上方「行業下的股票代碼」區塊，禁止編造未出現的股票代碼
- 禁止使用訓練記憶中的 A 股股票列表或行業歸屬
- 如果行情新聞中提到的利好行業在數據庫中找不到匹配，在 reasoning 中說明「數據庫中無匹配行業」而非強行匹配
- reasoning 必須說明：從新聞哪句話提取了關鍵詞 + 匹配到數據庫哪個行業"""

PROMPT_TEMPLATE = """請根據行情新聞分析結果，結合數據庫行業數據，篩選利好行業的股票。

## 行情新聞分析
{market_news}

## 最新交易日行業強弱（按平均漲跌幅排序）
{industry_daily}

## 數據庫中的行業列表
{industry_list}

## 行業下的股票代碼（抽樣）
{industry_stocks}

## 行業景氣度（綜合評分，0-100，越高越強）
{prosperity_data}

## 行業輪動預測（未來領漲行業預測）
{rotation_data}

{few_shot}

## 你的任務
1. 從行情新聞中識別利好行業關鍵詞（如「半導體」「新能源」「醫藥」）
2. 結合「最新交易日行業強弱」：若新聞提到的行業同時出現在領漲前列，優先納入 favorable_industries
3. 將關鍵詞與上方「數據庫中的行業列表」模糊匹配（如「半導體」→「C39電子設備製造」）
4. 從匹配行業的股票代碼中選取，filtered_codes 最多 50 個
5. 參考「行業景氣度」：景氣度 > 70 的行業優先納入 favorable_industries
6. 參考「行業輪動預測」：預測為領漲的行業優先納入

【市場概念→行業映射】
如果行情新聞中使用的是市場風格概念而非具體行業，按以下映射轉換後再匹配：
|- 「中小盤」「成長風格」→ 搜索數據庫中電子、計算機、醫藥、新能源等成長型行業
|- 「大盤藍籌」「權重股」→ 搜索數據庫中銀行、保險、證券、石油、電力等價值型行業
|- 「深市主機板」「滬市綜合」→ 這些是市場指數概念，不是行業，不要直接匹配
|- 「創業板」「科創板」→ 這些是板塊概念，搜索數據庫中科技、醫藥、高端製造等行業
|- 如果新聞中只提到市場概念而無具體行業，在 reasoning 中說明，並嘗試從新聞上下文推斷可能受益的行業

【數據引用要求】
- favorable_industries 必須是上方「數據庫中的行業列表」中存在的完整名稱
- filtered_codes 必須來自上方「行業下的股票代碼」區塊中對應行業的代碼
- 禁止編造未在輸入中出現的行業名稱或股票代碼
- 禁止使用訓練記憶中的股票列表
- 如果新聞提到的行業在數據庫中無匹配，reasoning 中說明並返回空列表
- 如果行情新聞的 bullish_factors 為空列表，說明上游 AI 未能識別具體行業，此時應從新聞文本中自行提取行業關鍵詞嘗試匹配

請嚴格按以下 JSON 格式返回（不要加 markdown 代碼塊標記）:
{{
  "reasoning": "分析理由（1-2句話，說明從新聞提取的關鍵詞 + 匹配到數據庫哪個行業）",
  "favorable_industries": ["數據庫行業全名1", "數據庫行業全名2"],
  "filtered_codes": ["sh.600000", "sz.000001"]
}}

注意:
- filtered_codes 最多 50 個，優先選龍頭股
- 如果無法匹配到利好行業，返回空列表
- 行業名稱必須用數據庫中的完整名稱（如 "C39電子設備製造"）
- JSON 中不要加 ```json 標記
- 禁止編造未在輸入中出現的行業或股票代碼"""


class IndustryAnalysisStage(BaseStage):
    """AI 0.5: 行業分析節點 — 行業篩選。"""

    def __init__(self):
        super().__init__(stage_name="industry_analysis", display_name="AI 0.5 · 行業分析")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行行業分析。

        kwargs:
            market_news: str — AI 0 的行情新聞分析結果（JSON 字符串）
        """
        market_news = kwargs.get("market_news", "")

        # 從 AI 0 的 JSON 輸出中結構化提取利好/利空行業，而非截斷整個 JSON
        market_news_summary = _extract_ai0_industry_signals(market_news)

        # === 從後端獲取最新交易日行業聚合 ===
        logger.info("[AI0.5] 獲取行業日聚合...")
        industry_daily = await market_data_client._get_industry_daily()
        industry_daily_text = _format_industry_daily(industry_daily)

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

        # === 獲取行業景氣度 ===
        logger.info("[AI0.5] 獲取行業景氣度...")
        prosperity_text = ""
        try:
            prosperity = await backend_client.get_industry_prosperity()
            prosperity_text = _format_prosperity(prosperity)
        except Exception as e:
            logger.warning(f"[AI0.5] 景氣度獲取失敗: {e}")
            prosperity_text = "數據不足，無法提供景氣度"

        # === 獲取輪動預測 ===
        logger.info("[AI0.5] 獲取輪動預測...")
        rotation_text = ""
        try:
            rotation = await backend_client.get_rotation_prediction(lookback_days=20)
            rotation_text = _format_rotation_prediction(rotation)
        except Exception as e:
            logger.warning(f"[AI0.5] 輪動預測獲取失敗: {e}")
            rotation_text = "數據不足，無法提供輪動預測"

        # === 工具調用：用 local_market_data 補充行業景氣度數據（記錄引用出處）===
        try:
            tool_result = await self._call_tool(
                "local_market_data",
                action="industry_prosperity",
            )
            if tool_result.success and tool_result.content:
                # 將工具返回的景氣度數據追加到 prompt 中
                prosperity_text += f"\n\n### 工具補充景氣度（local_market_data）\n{tool_result.content[:500]}"
                logger.info(f"[AI0.5] 工具補充景氣度: {len(tool_result.citations)} 條引用")
        except Exception as e:
            logger.debug(f"[AI0.5] 工具調用 local_market_data 失敗（非致命）: {e}")

        prompt = PROMPT_TEMPLATE.format(
            market_news=market_news_summary,  # 結構化摘要而非截斷原文
            industry_daily=industry_daily_text,
            industry_list=json.dumps(industry_list[:50], ensure_ascii=False, indent=2),
            industry_stocks=json.dumps(industry_stocks, ensure_ascii=False, indent=2),
            prosperity_data=prosperity_text,
            rotation_data=rotation_text,
            few_shot=get_few_shot("industry_analysis"),
        )

        # 注入工具調用引用來源（確保數據真實性可追溯）
        citations_summary = self._get_tool_citations_summary()
        if citations_summary:
            prompt += f"\n\n{citations_summary}"

        response = await self._call_llm(SYSTEM_PROMPT, prompt, json_mode=True)
        logger.info(f"[AI0.5 行業分析] {response[:100]}...")
        return response


def _extract_ai0_industry_signals(market_news: str) -> str:
    """從 AI 0 的 JSON 輸出中結構化提取行業利好/利空信號。

    只提取與行業分析相關的字段（bullish_factors / bearish_factors / stock_selection_advice），
    而非截斷整個 JSON，減少 token 消耗並提高信號精度。

    使用 extract_json() 穩健提取，容忍 sanitize_output() 添加的免責聲明尾部文本。
    """
    if not market_news or market_news == "無":
        return "無（AI 0 未提供分析結果）"

    from app.utils.json_extractor import extract_json

    data = extract_json(market_news)
    if data is None:
        logger.warning("[AI0.5] AI 0 JSON 提取失敗（所有降級策略均未成功），降級為截斷原文")
        return market_news[:1500] if market_news else "無"

    try:
        lines = []

        # 利好行業（含持續性判斷）
        bullish = data.get("bullish_factors", [])
        if bullish:
            lines.append("AI 0 識別的利好行業:")
            for b in bullish[:4]:
                sector = b.get("sector", "")
                continuity = b.get("continuity", "未知")
                cum = b.get("cumulative_change", 0)
                supported = b.get("supported_by_news", False)
                news_flag = "✓有新聞支撐" if supported else "✗無新聞支撐"
                lines.append(f"  {sector}: 累計{cum:+.1f}%, {continuity}, {news_flag}")

        # 利空行業（含利空性質）
        bearish = data.get("bearish_factors", [])
        if bearish:
            lines.append("AI 0 識別的利空行業:")
            for b in bearish[:3]:
                sector = b.get("sector", "")
                nature = b.get("nature", "未知")
                cum = b.get("cumulative_change", 0)
                lines.append(f"  {sector}: 累計{cum:+.1f}%, {nature}")

        # 選股建議
        advice = data.get("stock_selection_advice", "")
        if advice:
            lines.append(f"AI 0 選股建議: {advice[:300]}")

        return "\n".join(lines) if lines else "AI 0 分析結果中無行業信號"
    except (KeyError, TypeError) as e:
        logger.warning(f"[AI0.5] AI 0 JSON 字段提取失敗，降級為截斷原文: {e}")
        return market_news[:1500] if market_news else "無"


def _format_industry_daily(data: list[dict[str, Any]]) -> str:
    """格式化行業日聚合數據為 prompt 可讀文本。"""
    if not data:
        return "數據不足，無法提供行業聚合"

    lines = [f"交易日: {data[0].get('tradeDate', '')}", ""]
    lines.append("行業名稱 | 平均漲跌幅(%) | 上漲家數 | 下跌家數 | 總成交金額 | 個股數")
    # 取前 15 強勢 + 後 5 弱勢，避免 token 過多
    for item in data[:15] + data[-5:]:
        industry = item.get("industry", "")
        avg = item.get("avgPctChg")
        avg_str = f"{avg:.4f}" if avg is not None else "N/A"
        rising = item.get("risingCount", 0)
        falling = item.get("fallingCount", 0)
        amount = item.get("totalAmount")
        amount_str = f"{amount:.2f}" if amount is not None else "N/A"
        count = item.get("stockCount", 0)
        lines.append(f"{industry} | {avg_str} | {rising} | {falling} | {amount_str} | {count}")

    return "\n".join(lines)


def _format_prosperity(data: list[dict[str, Any]]) -> str:
    """格式化行業景氣度數據為 prompt 可讀文本（取前 15 強）。"""
    if not data:
        return "數據不足，無法提供景氣度"

    lines = ["行業名 | 景氣度 | 等級 | 動量分 | 資金分 | 活躍分 | 廣度分"]
    for item in data[:15]:
        industry = item.get("industry", "")
        index = item.get("prosperityIndex", 0)
        grade = item.get("grade", "")
        momentum = item.get("momentumScore", 0)
        capital = item.get("capitalScore", 0)
        activity = item.get("activityScore", 0)
        breadth = item.get("breadthScore", 0)
        lines.append(
            f"{industry} | {index:.1f} | {grade} | {momentum:.1f} | {capital:.1f} | {activity:.1f} | {breadth:.1f}"
        )

    return "\n".join(lines)


def _format_rotation_prediction(data: dict[str, Any]) -> str:
    """格式化輪動預測數據為 prompt 可讀文本。"""
    if not data:
        return "數據不足，無法提供輪動預測"

    lines = []
    confidence = data.get("confidence", 0)
    lines.append(f"預測信心度: {confidence:.1f}%")
    lines.append("")

    leaders = data.get("predictedLeaders", [])
    if leaders:
        lines.append("預測領漲行業:")
        for ind in leaders[:5]:
            name = ind.get("industry", "")
            score = ind.get("score", 0)
            momentum = ind.get("momentumScore", 0)
            capital = ind.get("capitalScore", 0)
            trend = ind.get("trendScore", 0)
            lines.append(
                f"- {name}: 評分 {score:.1f} (動量{momentum:.0f}/資金{capital:.0f}/趨勢{trend:.0f})"
            )

    laggards = data.get("predictedLaggards", [])
    if laggards:
        lines.append("")
        lines.append("預測滯後行業（建議避開）:")
        for ind in laggards[:3]:
            name = ind.get("industry", "")
            score = ind.get("score", 0)
            lines.append(f"- {name}: 評分 {score:.1f}")

    return "\n".join(lines)


def parse_industry_output(response: str) -> dict[str, Any]:
    """解析行業分析 AI 的 JSON 輸出 — 使用穩健的多級降級提取。"""
    from app.utils.json_extractor import extract_json

    data = extract_json(response)
    if data is not None:
        return data

    raise ValueError(f"無法從行業分析 AI 響應中提取 JSON（已嘗試所有降級策略）: {response[:200]}")
