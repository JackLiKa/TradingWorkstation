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

## 市場形態策略指引（必須遵循）
{regime_guidance}

## 持續性利好新聞池（選股應優先從此池相關行業/個股中選擇）
{bullish_pool_text}

## 持續性利空新聞池（選股應避開此池相關行業/個股）
{bearish_pool_text}

## 最新交易日行業強弱
{industry_text}

## 上一輪反思結論
{prev_reflection}

## 下一輪提示詞指引（必須遵循）
{next_prompt}

## 當前選股條件
{current_criteria}

## 回測配置（不可修改）
{config}

## 歷史優化記錄
{history_text}

{repetition_warning}

{rag_experiences}

{error_lessons}

{correlation_text}

{prosperity_text}

{migration_text}

{rotation_prediction_text}

{few_shot}

## 你的任務
1. **【強制】必須遵循上方「下一輪提示詞指引」中的改進方向**——若 next_prompt 指出要擴展行業/加止損/降低調倉，你必須在 criteria 中體現這些改動，不可忽略
2. **【強制】不可原樣輸出當前選股條件**——若上方有「⚠️重複警告」，你必須改變至少 1 個與重複輪不同的參數，打破死循環
3. **【利好池選股】**若上方「持續性利好新聞池」非空，優先在 criteria 的 industries 中選擇利好新聞涉及的行業；若「持續性利空新聞池」非空，避開利空新聞涉及的行業
4. 根據上方「市場分析」「最新交易日行業強弱」和「上一輪反思結論」，調整選股條件
5. 若領漲行業動能強勁，可適當提高 minPctChange / minReturn20 / minTurn 等動量條件，捕捉強勢股
6. 若市場由弱勢行業主導或防禦信號明顯，則偏向低波動、低換手或高紅利風格
6. **行業聚焦**：若某些行業連續多日領漲且資金集中，可在 criteria 中加入 "industries": ["行業名稱1", "行業名稱2"] 限制選股範圍至這些強勢行業（最多 3 個）；若無明確行業偏好則不要填寫 industries 字段。**重要**：若上方「行業相關性分析」指出某些行業對高度相關（相關係數 ≥ 0.7），應避免在 industries 中同時選擇這些高相關行業，以保持組合分散度。**優先參考**：上方「行業景氣度指標」中景氣度 ≥ 65 的「繁榮」或「景氣」等級行業是更可靠的聚焦目標，避免選擇「低迷」或「衰退」等級行業
7. 參考上方「歷史優化記錄」和 RAG 經驗（如有），避免重複歷史上效果差的策略
8. 如有「歷史錯誤教訓」，確保不重複同類錯誤（特別是 JSON 格式錯誤）
9. 每次只調整 1-3 個參數，不要大幅變動
10. reasoning 必須說明：為何調整這些參數 + 預期效果 + 是否參考強勢行業 + 是否借鑒了歷史經驗 + 若使用 industries 需說明為何聚焦這些行業 + **如何遵循了 next_prompt 的指引**

【超短線交易鐵律 — 避免空倉「假穩健」】
- 策略必須產生實際交易（totalTrades > 0），0 交易 = 策略無功能，評分會被嚴重懲罰
- 若上方「歷史優化記錄」中某輪交易=0筆且標記 ⚠️空倉，該輪條件過度收斂，必須放寬
- 超短線核心：高換手（minTurn ≥ 3）、量價齊升（minVolumeRatio ≥ 1.0）、短期動能（minPctChange ≥ 1 或 minReturn20 ≥ 5）
- 避免同時疊加過多過濾條件（如 maxRsi14 ≤ 30 + priceAboveMa60 + 單一行業），這會導致候選股不足而無交易
- 行業聚焦最多 2 個，且優先選擇景氣度 ≥ 65 的強勢行業；若歷史顯示單一行業導致 0 交易，立即擴展至 2-3 個行業或移除行業限制
- 振幅上限 maxAmplitude 不宜過低（≤ 3% 會過濾掉大部分活躍股），建議 ≥ 4%

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
            regime_type: str — 當前市場形態類型（trending_up/trending_down/oscillation/...）
        """
        market_context = kwargs.get("market_context", "")
        current_criteria = kwargs.get("current_criteria", {})
        config = kwargs.get("config", {})
        history = kwargs.get("history", [])
        prev_reflection = kwargs.get("prev_reflection", "")
        next_prompt = kwargs.get("next_prompt", "")
        rag_experiences = kwargs.get("rag_experiences", "")
        regime_type = kwargs.get("regime_type", "unknown")

        # 構建歷史摘要（含重複檢測）
        history_text = ""
        repetition_count = 0
        last_criteria_signature = ""
        for h in history[-5:]:
            stats = h.backtest_statistics
            active_filters = {
                k: v for k, v in h.criteria.items() if v is not None and v is not False and v != "any" and v != 0
            }
            trades = stats.get("totalTrades", 0)
            trade_tag = f", 交易={trades}筆" + (" ⚠️空倉" if trades == 0 else "")
            # 計算 criteria 簽名以檢測重複
            criteria_sig = json.dumps(active_filters, ensure_ascii=False, sort_keys=True)
            is_repeat = criteria_sig == last_criteria_signature
            if is_repeat:
                repetition_count += 1
            repeat_tag = " ⚠️重複" if is_repeat else ""
            history_text += (
                f"  第{h.iteration}輪: 評分={h.composite_score}, 收益={stats.get('totalReturn', 0)}%, "
                f"回撤={stats.get('maxDrawdown', 0)}%, 夏普={stats.get('sharpe', 0)}, "
                f"超額={stats.get('excessReturn', 0)}%{trade_tag}{repeat_tag}, "
                f"條件={json.dumps(active_filters, ensure_ascii=False)}\n"
            )
            last_criteria_signature = criteria_sig

        # 構建重複警告（連續 2+ 輪相同則注入強變異指引）
        repetition_warning = ""
        if repetition_count >= 2:
            repetition_warning = (
                "## ⚠️ 重複策略警告（連續 {n} 輪生成相同策略）\n"
                "上方歷史記錄中連續多輪生成完全相同的選股條件，這是死循環！\n"
                "你必須打破這個循環，採取以下強變異措施之一：\n"
                "- 若當前 industries 只有 1 個行業，立即擴展至 2-3 個景氣度 ≥ 65 的強勢行業\n"
                "- 若 stopLossPct 為 null，立即設置 stopLossPct=8（加止損）\n"
                "- 若 rebalanceInterval ≤ 5，立即改為 10 或 15（降低調倉頻率）\n"
                "- 調整 minTurn（當前值 ±2.0）或 minVolumeRatio（當前值 ±0.3）\n"
                "- 移除或放寬最嚴格的過濾條件（如 maxRsi14、maxAmplitude）\n"
                "reasoning 中必須明確說明你採取了哪項強變異措施及其理由\n"
            ).format(n=repetition_count + 1)
        elif repetition_count == 1:
            repetition_warning = (
                "## ⚠️ 重複策略提示\n"
                "上一輪與再上一輪生成了相同策略，請確保本輪有實質性參數調整。\n"
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

        # 獲取行業相關性分析，避免高相關行業過度集中
        logger.info("[AI2] 獲取行業相關性分析...")
        try:
            corr_data = await market_data_client.get_industry_correlation(days=30)
            correlation_text = corr_data.get("text", "")
        except Exception as e:
            logger.warning(f"[AI2] 行業相關性分析失敗: {e}")
            correlation_text = ""

        # 獲取行業景氣度指標，輔助 AI 選擇強勢行業
        logger.info("[AI2] 獲取行業景氣度指標...")
        try:
            prosperity_data = await market_data_client.get_industry_prosperity()
            prosperity_text = prosperity_data.get("text", "")
        except Exception as e:
            logger.warning(f"[AI2] 行業景氣度獲取失敗: {e}")
            prosperity_text = ""

        # 獲取資金流向遷移分析，輔助 AI 參考資金遷移方向
        logger.info("[AI2] 獲取資金流向遷移分析...")
        try:
            migration_data = await market_data_client.get_capital_migration(days=10)
            migration_text = migration_data.get("text", "")
        except Exception as e:
            logger.warning(f"[AI2] 資金遷移分析失敗: {e}")
            migration_text = ""

        # 獲取行業輪動預測，輔助 AI 參考輪動預測選擇行業
        logger.info("[AI2] 獲取行業輪動預測...")
        try:
            rotation_pred = await market_data_client.get_rotation_prediction(lookback_days=20)
            rotation_prediction_text = rotation_pred.get("text", "")
        except Exception as e:
            logger.warning(f"[AI2] 輪動預測獲取失敗: {e}")
            rotation_prediction_text = ""

        # 注入歷史錯誤教訓（避免重複犯錯）
        from app.services import error_store

        error_lessons = error_store.format_errors_for_prompt("strategy_generation", limit=3)

        # 構建市場形態策略指引
        from app.services.regime_strategy import get_regime_strategy_guidance

        regime_guidance = get_regime_strategy_guidance(regime_type)

        # 獲取利好池/利空池（持續性利好/利空新聞，用於選股方向引導）
        bullish_pool_text = "無（尚無持續性利好新聞評分）"
        bearish_pool_text = "無（尚無持續性利空新聞評分）"
        try:
            from app.services import news_store

            bullish = await news_store.get_bullish_pool(days_back=7, limit=10)
            bearish = await news_store.get_bearish_pool(days_back=7, limit=10)
            if bullish:
                bullish_lines = []
                for item in bullish[:10]:
                    bullish_lines.append(
                        f"- [{item.get('news_label', '')}] {item.get('title', '')} "
                        f"(方向={item.get('direction')}, 持續性={item.get('sustainability')})"
                    )
                bullish_pool_text = "\n".join(bullish_lines)
            if bearish:
                bearish_lines = []
                for item in bearish[:10]:
                    bearish_lines.append(
                        f"- [{item.get('news_label', '')}] {item.get('title', '')} "
                        f"(方向={item.get('direction')}, 持續性={item.get('sustainability')})"
                    )
                bearish_pool_text = "\n".join(bearish_lines)
        except Exception as e:
            logger.warning(f"[AI2] 利好/利空池獲取失敗: {e}")

        prompt = PROMPT_TEMPLATE.format(
            market_context=market_context,
            regime_guidance=regime_guidance,
            bullish_pool_text=bullish_pool_text,
            bearish_pool_text=bearish_pool_text,
            industry_text=industry_text,
            prev_reflection=prev_reflection if prev_reflection else "無",
            next_prompt=next_prompt if next_prompt else "無（按你的判斷生成）",
            current_criteria=json.dumps(current_criteria, ensure_ascii=False, indent=2),
            config=json.dumps(config, ensure_ascii=False, indent=2),
            history_text=history_text if history_text else "無（首輪）",
            repetition_warning=repetition_warning,
            rag_experiences=rag_experiences if rag_experiences else "無（RAG 不可用或無相似經驗）",
            error_lessons=error_lessons if error_lessons else "無（無歷史錯誤記錄）",
            correlation_text=correlation_text if correlation_text else "無（無高相關行業對或數據不足）",
            prosperity_text=prosperity_text if prosperity_text else "無（景氣度數據不足）",
            migration_text=migration_text if migration_text else "無（資金遷移數據不足）",
            rotation_prediction_text=rotation_prediction_text if rotation_prediction_text else "無（輪動預測數據不足）",
            asof_date=asof_date,
            adjustflag=adjustflag,
            few_shot=get_few_shot("strategy_generation"),
        )

        # === Prompt 長度控制 — 避免推理模型因輸入過長導致推理 token 耗盡 ===
        # 策略生成 prompt 含 15+ 數據區塊，全量注入可能超過 8000 token
        # 推理模型（deepseek-reasoner）的推理 token 也計入 max_tokens，
        # 輸入過長 → 推理過長 → 推理用完 token → 輸出為空
        # 策略：按優先級精簡低價值區塊（保留核心，截斷輔助）
        MAX_PROMPT_CHARS = 12000  # 約 4000 token，留足推理 + 輸出空間
        if len(prompt) > MAX_PROMPT_CHARS:
            logger.warning(
                f"[AI2] prompt 過長（{len(prompt)} 字 > {MAX_PROMPT_CHARS}），精簡低優先級區塊"
            )
            # 按優先級從低到高截斷（這些是「有則更好」的輔助數據）
            # 優先級：migration < rotation < correlation < prosperity < rag < error_lessons
            # 核心（不可截斷）：market_context, regime_guidance, industry_text, prev_reflection,
            #                  next_prompt, current_criteria, config, history_text, few_shot, JSON schema
            truncation_targets = [
                ("## 資金流向遷移分析", migration_text, "無（已精簡）"),
                ("## 行業輪動預測", rotation_prediction_text, "無（已精簡）"),
                ("## 行業相關性分析", correlation_text, "無（已精簡）"),
                ("## 行業景氣度指標", prosperity_text, "無（已精簡）"),
                ("## RAG 歷史經驗", rag_experiences, "無（已精簡）"),
            ]
            for section_header, original_text, replacement in truncation_targets:
                if len(prompt) <= MAX_PROMPT_CHARS:
                    break
                if original_text and len(original_text) > 100:
                    # 截斷該區塊到 200 字摘要
                    truncated = original_text[:200] + "...（已精簡，完整數據省略）"
                    prompt = prompt.replace(original_text, truncated)
                    logger.info(f"[AI2] 精簡 {section_header}: {len(original_text)} → {len(truncated)} 字")

        # === 工具調用：用 local_market_data 補充選股數據（記錄引用出處）===
        try:
            tool_result = await self._call_tool(
                "local_market_data",
                action="screener",
                conditions={},
                limit=10,
            )
            if tool_result.success and tool_result.content:
                prompt += f"\n\n### 工具補充選股數據（local_market_data）\n{tool_result.content[:500]}"
                logger.info(f"[AI2] 工具補充選股: {len(tool_result.citations)} 條引用")
        except Exception as e:
            logger.debug(f"[AI2] 工具調用 local_market_data 失敗（非致命）: {e}")

        # 注入工具調用引用來源（確保數據真實性可追溯）
        citations_summary = self._get_tool_citations_summary()
        if citations_summary:
            prompt += f"\n\n{citations_summary}"

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
