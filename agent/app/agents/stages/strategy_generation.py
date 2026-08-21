"""AI 2: 策略生成 — 根據市場狀態 + 歷史策略，生成選股條件。

輸入: 市場分析、當前選股條件、回測配置、歷史記錄、上一輪反思、下一輪提示詞
輸出: JSON { reasoning, criteria }
範式: 必須是有效 JSON，包含 reasoning 和 criteria 字段
"""

import json
import logging
from typing import Any

from app.agents.few_shot import get_few_shot
from app.agents.stages.base import BaseStage
from app.services.market_data_client import market_data_client

logger = logging.getLogger("agent.stage.strategy")

SYSTEM_PROMPT = """你是一個專業的量化策略設計師，擅長 A 股選股策略設計和參數調優。

【數據真實性鐵律】
- reasoning 中引用的市場數據、歷史評分、回測指標必須來自上方 prompt 提供的輸入
- 禁止編造未在輸入中出現的歷史回測結果、市場數據、個股表現
- 禁止引用訓練記憶中的 A 股歷史行情或個股數據來支撐調整理由
- 調整理由必須基於上方「市場分析」「上一輪反思結論」「歷史優化記錄」中的具體內容
- 如果引用歷史經驗，必須是上方 RAG 區塊中實際提供的經驗，不要編造經驗"""

PROMPT_TEMPLATE = """你是一個量化策略設計師。請根據市場分析結果生成選股條件。

## 市場分析
{market_context}

## 最新交易日行業強弱
{industry_text}

## 上一輪反思結論
{prev_reflection}

## 下一輪提示詞指引
{next_prompt}

## 當前選股條件
{current_criteria}

## 回測配置（不可修改）
{config}

## 歷史優化記錄
{history_text}

{rag_experiences}

{error_lessons}

{few_shot}

## 你的任務
1. 根據上方「市場分析」「最新交易日行業強弱」和「上一輪反思結論」，調整選股條件
2. 若領漲行業動能強勁，可適當提高 minPctChange / minReturn20 / minTurn 等動量條件，捕捉強勢股
3. 若市場由弱勢行業主導或防禦信號明顯，則偏向低波動、低換手或高紅利風格
4. **行業聚焦**：若某些行業連續多日領漲且資金集中，可在 criteria 中加入 "industries": ["行業名稱1", "行業名稱2"] 限制選股範圍至這些強勢行業（最多 3 個）；若無明確行業偏好則不要填寫 industries 字段
5. 參考上方「歷史優化記錄」和 RAG 經驗（如有），避免重複歷史上效果差的策略
6. 如有「歷史錯誤教訓」，確保不重複同類錯誤（特別是 JSON 格式錯誤）
7. 每次只調整 1-3 個參數，不要大幅變動
8. reasoning 必須說明：為何調整這些參數 + 預期效果 + 是否參考強勢行業 + 是否借鑒了歷史經驗 + 若使用 industries 需說明為何聚焦這些行業

【數據引用要求】
- reasoning 中引用的市場狀況必須來自上方「市場分析」區塊
- reasoning 中引用的歷史評分/收益/回撤必須來自上方「歷史優化記錄」區塊
- reasoning 中引用的歷史經驗必須來自上方 RAG 區塊，禁止編造未提供的經驗
- 禁止引用訓練記憶中的 A 股歷史行情、個股數據、政策事件
- 如果上方輸入數據不足，在 reasoning 中標註「數據不足」而非編造

請嚴格按以下 JSON 格式返回（不要加 markdown 代碼塊標記）:
{{
  "reasoning": "調整理由（2-3句話，說明為何調整這些參數及預期效果，引用上方輸入中的具體數據）",
  "criteria": {{
    "asOfDate": "{asof_date}",
    "adjustflag": {adjustflag},
    "excludeSt": true,
    "maxResults": 50,
    "sortBy": "score",
    "minClose": null,
    "maxClose": null,
    "minPctChange": null,
    "maxPctChange": null,
    "minTurn": null,
    "maxTurn": null,
    "minAmplitude": null,
    "maxAmplitude": null,
    "minVolume": null,
    "minAmount": null,
    "minVolumeRatio": null,
    "maxVolumeRatio": null,
    "minReturn20": null,
    "maxReturn20": null,
    "minReturn60": null,
    "maxReturn60": null,
    "minReturn120": null,
    "maxReturn120": null,
    "minRsi14": null,
    "maxRsi14": null,
    "minKValue": null,
    "maxKValue": null,
    "minJValue": null,
    "maxJValue": null,
    "minMacdHist": null,
    "maxMacdHist": null,
    "macdCrossSignal": "any",
    "macdCrossWithinDays": 0,
    "kdjCrossSignal": "any",
    "kdjCrossWithinDays": 0,
    "bollPosition": "any",
    "priceAboveMa5": false,
    "priceAboveMa20": false,
    "priceAboveMa60": false,
    "ma5AboveMa20": false,
    "ma20AboveMa60": false,
    "industries": null
  }}
}}

注意:
- 數值參數用數字或 null，不要用字符串
- 信號字段用 "any"/"golden_cross"/"death_cross"/"none"
- 布爾字段用 true/false
- industries 字段：若需聚焦強勢行業則填寫行業名稱數組（如 ["B09有色金属矿采选业"]），否則填 null
- 行業名稱必須完全匹配上方「最新交易日行業強弱」表格中的「行業名稱」列，禁止編造或縮寫
- 只調整選股條件，不要改變回測配置
- JSON 中不要加 ```json 標記
- 只填寫需要調整的字段，其餘保持 null/false/"any"
- 常用參數範圍參考: minTurn 0.5-5.0, minVolumeRatio 0.5-3.0, minReturn20 -10~20, minRsi14 20-80, macdCrossWithinDays 1-10
- reasoning 中禁止編造未在上方輸入中出現的數據"""


class StrategyGenerationStage(BaseStage):
    """AI 2: 策略生成節點。"""

    def __init__(self):
        super().__init__(stage_name="strategy_generation", display_name="AI 2 · 策略生成")

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    async def execute(self, **kwargs) -> str:
        """執行策略生成。

        kwargs:
            market_context: str — 市場分析結果
            current_criteria: dict — 當前選股條件
            config: dict — 回測配置
            history: list[IterationResult] — 歷史記錄
            prev_reflection: str — 上一輪反思
            next_prompt: str — 下一輪提示詞指引
            rag_experiences: str — RAG 檢索的歷史經驗文本（可選）
        """
        market_context = kwargs.get("market_context", "")
        current_criteria = kwargs.get("current_criteria", {})
        config = kwargs.get("config", {})
        history = kwargs.get("history", [])
        prev_reflection = kwargs.get("prev_reflection", "")
        next_prompt = kwargs.get("next_prompt", "")
        rag_experiences = kwargs.get("rag_experiences", "")

        # 構建歷史摘要
        history_text = ""
        for h in history[-5:]:
            stats = h.backtest_statistics
            active_filters = {
                k: v for k, v in h.criteria.items() if v is not None and v is not False and v != "any" and v != 0
            }
            history_text += (
                f"  第{h.iteration}輪: 評分={h.composite_score}, 收益={stats.get('totalReturn', 0)}%, "
                f"回撤={stats.get('maxDrawdown', 0)}%, 夏普={stats.get('sharpe', 0)}, "
                f"條件={json.dumps(active_filters, ensure_ascii=False)}\n"
            )

        from datetime import datetime

        asof_date = current_criteria.get("asOfDate", datetime.now().strftime("%Y-%m-%d"))
        adjustflag = current_criteria.get("adjustflag", 3)

        # 獲取最新交易日行業強弱，輔助策略生成
        logger.info("[AI2] 獲取行業日聚合...")
        try:
            industry_daily = await market_data_client._get_industry_daily()
            industry_text = _format_industry_daily(industry_daily)
        except Exception as e:
            logger.warning(f"[AI2] 獲取行業聚合失敗: {e}")
            industry_text = "數據不足，無法提供行業聚合"

        # 注入歷史錯誤教訓（避免重複犯錯）
        from app.services import error_store

        error_lessons = error_store.format_errors_for_prompt("strategy_generation", limit=3)

        prompt = PROMPT_TEMPLATE.format(
            market_context=market_context,
            industry_text=industry_text,
            prev_reflection=prev_reflection if prev_reflection else "無",
            next_prompt=next_prompt if next_prompt else "無（按你的判斷生成）",
            current_criteria=json.dumps(current_criteria, ensure_ascii=False, indent=2),
            config=json.dumps(config, ensure_ascii=False, indent=2),
            history_text=history_text if history_text else "無（首輪）",
            rag_experiences=rag_experiences if rag_experiences else "無（RAG 不可用或無相似經驗）",
            error_lessons=error_lessons if error_lessons else "無（無歷史錯誤記錄）",
            asof_date=asof_date,
            adjustflag=adjustflag,
            few_shot=get_few_shot("strategy_generation"),
        )

        response = await self._call_llm(SYSTEM_PROMPT, prompt, json_mode=True)
        logger.info(f"[AI2 策略生成] {response[:100]}...")
        return response


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


def parse_strategy_output(response: str) -> dict[str, Any]:
    """解析策略生成 AI 的 JSON 輸出 — 使用穩健的多級降級提取。

    降級策略：
    1. 直接解析 / ```json 代碼塊 / 棧匹配 / 逐候選 / 修復常見錯誤
    2. 全部失敗 → 拋出 ValueError（由 base.py 重試機制處理）
    """
    from app.utils.json_extractor import extract_json

    data = extract_json(response)
    if data is not None:
        return data

    raise ValueError(f"無法從 LLM 響應中提取 JSON（已嘗試所有降級策略）: {response[:200]}")
