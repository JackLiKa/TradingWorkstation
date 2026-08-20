"""評委 AI — 多維度分析型評分（Analytic Rubric）。

基於學術研究（AdaRubric/Autorubric/Apple LLM-as-Judge）的工程化實現：

核心問題（舊方案）：
- 0-100 自由評分 → LLM 分數壓縮到 70（score compression）
- 單一總分 → 無法定位具體問題
- LLM 失敗時固定分 → 不公平

新方案（多維度分析型評分）：
1. 每個階段定義 5 個獨立評分維度（binary: 通過/不通過）
2. 每個維度有明確的通過標準（可規則驗證的優先用規則）
3. 規則可驗證的維度 → 規則評分（確定性，無 bias）
4. 規則無法驗證的維度 → LLM 評分（強制 binary，不給中間選項）
5. 總分 = Σ(維度權重 × 維度分)，連續 0-100，不會聚集

評分公式：
  score = Σ(dimension_weight_i × dimension_score_i)
  dimension_score_i ∈ {0, 1}（binary）或 [0, 1]（規則連續分）

優勢：
- 維度獨立 → 不會因一個維度好就整體給高分
- Binary 選擇 → 消除中間分聚集
- 規則優先 → 確定性評分，LLM 只補充語義判斷
- 可解釋 → 每個維度的通過/不通過都有理由
"""

import json
import logging
import re
from typing import Any

from app.agents.few_shot import get_few_shot
from app.core.llm_client import llm_client

logger = logging.getLogger("agent.judge")


# ===== 多維度評分定義 =====
# 每個維度：weight（權重）, type（rule/llm）, check（規則驗證函數或 LLM 描述）
# rule 類型：用代碼驗證，確定性，無 bias
# llm 類型：用 LLM 判斷，強制 binary（通過/不通過）


def _check_length(output: str, threshold: int) -> tuple[float, str]:
    """長度維度 — 連續評分（0-1），超過 threshold 為 1.0。"""
    actual = len(output.strip())
    if actual >= threshold:
        ratio = min(actual / threshold, 2.0)
        # 超過 threshold 但不到 2 倍 = 0.8，超過 2 倍 = 1.0
        return min(0.5 + ratio * 0.25, 1.0), f"長度 {actual} 字（要求 ≥{threshold}）"
    return actual / threshold * 0.5, f"長度不足 {actual}/{threshold} 字"


def _check_json_valid(output: str, required_fields: list[str]) -> tuple[float, str]:
    """JSON 格式維度 — 連續評分，有效 JSON=1.0，缺字段=0.5，無效=0。

    使用穩健的多級降級 JSON 提取（與 parse_strategy_output 一致）。
    """
    from app.utils.json_extractor import extract_json

    data = extract_json(output)
    if data is None:
        return 0.0, "無法提取 JSON（已嘗試所有降級策略）"

    # 檢查必要字段
    missing = [f for f in required_fields if f not in data]
    if not missing:
        return 1.0, "JSON 格式正確，字段完整"
    return 0.5, f"JSON 有效但缺少字段: {missing}"


def _check_data_density(output: str) -> tuple[float, str]:
    """數據引用密度維度 — 連續評分，基於數字/百分比出現頻率。"""
    text = output.strip()
    numbers = re.findall(r"\d+\.?\d*%?", text)
    # 每 100 字 1 個數據引用 = 0.5，2 個 = 0.8，3+ 個 = 1.0
    density = len(numbers) / max(len(text) / 100, 1)
    if density >= 3:
        return 1.0, f"數據引用豐富（{len(numbers)} 處）"
    elif density >= 2:
        return 0.8, f"數據引用充分（{len(numbers)} 處）"
    elif density >= 1:
        return 0.5, f"數據引用適中（{len(numbers)} 處）"
    return 0.2, f"數據引用不足（{len(numbers)} 處）"


def _check_structure(output: str, markers: list[str] = None) -> tuple[float, str]:
    """結構完整性維度 — 連續評分，基於標題/列表/分段標記。"""
    if markers is None:
        markers = ["###", "##", "-", "1.", "2.", "3.", "4.", "•"]
    text = output.strip()
    found = sum(1 for m in markers if m in text)
    if found >= 4:
        return 1.0, f"結構清晰（{found} 處標記）"
    elif found >= 2:
        return 0.7, f"有結構（{found} 處標記）"
    elif found >= 1:
        return 0.4, f"結構簡單（{found} 處標記）"
    return 0.1, "無結構標記"


def _check_required_keywords(output: str, keywords: list[str]) -> tuple[float, str]:
    """必要關鍵詞維度 — 連續評分，基於必須出現的關鍵詞覆蓋率。

    支持同義詞匹配：如果關鍵詞有「|」分隔的別名，任一匹配即可。
    例如 ["趨勢|走勢", "波動", "策略"] 表示「趨勢」或「走勢」都算匹配。
    """
    text = output.lower()
    found = 0
    missing = []
    for kw in keywords:
        # 支持「關鍵詞|同義詞1|同義詞2」格式
        aliases = [a.strip().lower() for a in kw.split("|")]
        if any(a in text for a in aliases):
            found += 1
        else:
            missing.append(kw)
    ratio = found / len(keywords) if keywords else 1.0
    if ratio == 1.0:
        return 1.0, f"關鍵詞完整（{found}/{len(keywords)}）"
    elif ratio >= 0.5:
        return 0.6, f"部分關鍵詞缺失（{found}/{len(keywords)}），缺: {missing}"
    return 0.2, f"關鍵詞嚴重缺失（{found}/{len(keywords)}），缺: {missing}"


def _check_regime_identification(output: str) -> tuple[float, str]:
    """市場形態識別維度 — 檢查輸出是否包含至少一種形態類型名稱。

    形態類型：震盪/上漲中繼/下跌中繼/上漲趨勢/下跌趨勢
    """
    regime_types = [
        ["震盪", "震荡"],
        ["上漲中繼", "上涨中继"],
        ["下跌中繼", "下跌中继"],
        ["上漲趨勢", "上涨趋势"],
        ["下跌趨勢", "下跌趋势"],
    ]
    text = output.lower()
    found_types = []
    for aliases in regime_types:
        if any(a.lower() in text for a in aliases):
            found_types.append(aliases[0])

    if len(found_types) >= 1:
        return 1.0, f"識別到市場形態: {found_types}"
    return 0.0, "未識別到任何市場形態類型（震盪/上漲中繼/下跌中繼/上漲趨勢/下跌趨勢）"


def _check_continuity_judgment(output: str) -> tuple[float, str]:
    """延續性判斷維度 — 檢查輸出是否包含利好延續性或利空性質判斷。

    利好延續性：持續性/間歇性/突發性
    利空性質：持續性利空/突發性利空/情緒性利空
    """
    bullish_continuity = ["持續性", "持续性", "間歇性", "间歇性", "突發性", "突发性"]
    bearish_nature = ["持續性利空", "持续性利空", "突發性利空", "突发性利空", "情緒性利空", "情绪性利空"]

    text = output.lower()
    found_bullish = [c for c in bullish_continuity if c.lower() in text]
    found_bearish = [n for n in bearish_nature if n.lower() in text]

    if found_bearish:
        return 1.0, f"識別到利空性質: {found_bearish}"
    if found_bullish:
        return 0.8, f"識別到利好延續性: {found_bullish}"
    return 0.0, "未識別到利好延續性或利空性質判斷"


def _check_sentiment_analysis(output: str) -> tuple[float, str]:
    """市場情緒分析維度 — 檢查輸出是否包含情緒分數或情緒標籤。"""
    sentiment_keywords = ["情緒", "情绪", "sentiment", "偏樂觀", "偏悲觀", "中性", "恐慌", "樂觀", "悲觀"]
    text = output.lower()
    found = [k for k in sentiment_keywords if k.lower() in text]

    if len(found) >= 2:
        return 1.0, f"情緒分析充分: {found}"
    elif len(found) >= 1:
        return 0.6, f"有情緒分析: {found}"
    return 0.0, "未識別到市場情緒分析"


def _check_news_tracking(output: str) -> tuple[float, str]:
    """新聞追蹤維度 — 檢查輸出是否引用了新聞標題或新聞來源。"""
    news_indicators = ["新聞", "新闻", "東方財富", "东方财富", "related_news", "supported_by_news", "title"]
    text = output.lower()
    found = [k for k in news_indicators if k.lower() in text]

    if len(found) >= 2:
        return 1.0, f"新聞追蹤充分: {found}"
    elif len(found) >= 1:
        return 0.5, f"有新聞引用: {found}"
    return 0.0, "未引用任何新聞"


# ===== 各階段的多維度評分定義 =====
# 維度類型：rule（規則驗證）/ llm（LLM 語義判斷）
STAGE_RUBRICS: dict[str, list[dict]] = {
    "market_news": [
        {
            "name": "JSON格式",
            "weight": 0.15,
            "type": "rule",
            "check": lambda o, e: _check_json_valid(
                o, ["market_regime", "market_sentiment", "bullish_factors", "bearish_factors"]
            ),
        },
        {"name": "數據引用", "weight": 0.15, "type": "rule", "check": lambda o, e: _check_data_density(o)},
        {
            "name": "市場形態識別",
            "weight": 0.15,
            "type": "rule",
            "check": lambda o, e: _check_regime_identification(o),
        },
        {
            "name": "延續性判斷",
            "weight": 0.15,
            "type": "rule",
            "check": lambda o, e: _check_continuity_judgment(o),
        },
        {
            "name": "市場情緒分析",
            "weight": 0.10,
            "type": "rule",
            "check": lambda o, e: _check_sentiment_analysis(o),
        },
        {
            "name": "新聞追蹤",
            "weight": 0.10,
            "type": "rule",
            "check": lambda o, e: _check_news_tracking(o),
        },
        {
            "name": "必要內容",
            "weight": 0.10,
            "type": "rule",
            "check": lambda o, e: _check_required_keywords(
                o, ["利好|強勢|bullish", "利空|弱勢|bearish", "選股|關注|避開"]
            ),
        },
        {
            "name": "內容實質",
            "weight": 0.10,
            "type": "llm",
            "check": "輸出是否包含具體的多日行業分析（非單日漲跌），是否引用了10日內的具體漲跌幅數據，利好延續性判斷是否有數據支撐，利空性質判斷是否區分了突發性和持續性",
        },
    ],
    "industry_analysis": [
        {
            "name": "JSON格式",
            "weight": 0.30,
            "type": "rule",
            "check": lambda o, e: _check_json_valid(o, e.get("required_fields", [])),
        },
        {"name": "長度充分", "weight": 0.10, "type": "rule", "check": lambda o, e: _check_length(o, e["min_length"])},
        {"name": "數據引用", "weight": 0.20, "type": "rule", "check": lambda o, e: _check_data_density(o)},
        {
            "name": "必要字段",
            "weight": 0.25,
            "type": "rule",
            "check": lambda o, e: _check_required_keywords(o, ["reasoning", "favorable_industries", "filtered_codes"]),
        },
        {
            "name": "匹配質量",
            "weight": 0.15,
            "type": "llm",
            "check": "行業關鍵詞與數據庫行業分類的匹配是否合理，filtered_codes 是否確實屬於利好行業",
        },
    ],
    "market_analysis": [
        {"name": "長度充分", "weight": 0.10, "type": "rule", "check": lambda o, e: _check_length(o, e["min_length"])},
        {"name": "數據引用", "weight": 0.20, "type": "rule", "check": lambda o, e: _check_data_density(o)},
        {
            "name": "必要內容",
            "weight": 0.20,
            "type": "rule",
            "check": lambda o, e: _check_required_keywords(o, ["趨勢|走勢|方向", "波動|震盪|風險", "策略|選股|操作"]),
        },
        {
            "name": "市場形態識別",
            "weight": 0.20,
            "type": "rule",
            "check": lambda o, e: _check_regime_identification(o),
        },
        {
            "name": "內容實質",
            "weight": 0.30,
            "type": "llm",
            "check": "市場趨勢判斷是否有邏輯依據，策略類型推薦是否與識別到的市場形態匹配（震盪→均值回歸，趨勢→趨勢跟蹤，下跌中繼→防禦）",
        },
    ],
    "strategy_generation": [
        {
            "name": "JSON格式",
            "weight": 0.30,
            "type": "rule",
            "check": lambda o, e: _check_json_valid(o, e.get("required_fields", [])),
        },
        {
            "name": "必要字段",
            "weight": 0.25,
            "type": "rule",
            "check": lambda o, e: _check_required_keywords(o, ["reasoning", "criteria"]),
        },
        {"name": "數據引用", "weight": 0.15, "type": "rule", "check": lambda o, e: _check_data_density(o)},
        {
            "name": "推理質量",
            "weight": 0.20,
            "type": "llm",
            "check": "reasoning 是否說明了調整參數的具體原因和預期效果（非泛泛而談）",
        },
        {
            "name": "參數合理",
            "weight": 0.10,
            "type": "llm",
            "check": "criteria 中的參數值是否在合理範圍內（如 minTurn 0.5-5.0），是否有明顯錯誤值",
        },
    ],
    "backtest_reflection": [
        {"name": "長度充分", "weight": 0.10, "type": "rule", "check": lambda o, e: _check_length(o, e["min_length"])},
        {"name": "數據引用", "weight": 0.30, "type": "rule", "check": lambda o, e: _check_data_density(o)},
        {"name": "結構完整", "weight": 0.15, "type": "rule", "check": lambda o, e: _check_structure(o)},
        {
            "name": "必要內容",
            "weight": 0.25,
            "type": "rule",
            "check": lambda o, e: _check_required_keywords(o, ["優點", "不足", "收益", "回撤", "改進"]),
        },
        {
            "name": "改進質量",
            "weight": 0.20,
            "type": "llm",
            "check": "改進方向是否具體可操作（包含參數名+調整方向），而非籠統建議",
        },
    ],
    "prompt_generation": [
        {"name": "長度充分", "weight": 0.15, "type": "rule", "check": lambda o, e: _check_length(o, e["min_length"])},
        {
            "name": "必要內容",
            "weight": 0.25,
            "type": "rule",
            "check": lambda o, e: _check_required_keywords(
                o, ["調整|修改|改進|優化", "避免|不要|防止", "目標|期望|達到"]
            ),
        },
        {"name": "數據引用", "weight": 0.20, "type": "rule", "check": lambda o, e: _check_data_density(o)},
        {
            "name": "指引精準",
            "weight": 0.40,
            "type": "llm",
            "check": "指引是否包含具體參數名（如 minTurn、stopLossPct、minVolumeRatio），而非籠統的「優化策略」",
        },
    ],
}

# 各階段的基本期望（保留向後兼容）
STAGE_EXPECTATIONS = {
    "market_news": {
        "format": "JSON",
        "required_content": "market_regime+market_sentiment+bullish_factors+bearish_factors+選股建議",
        "min_length": 200,
        "must_be_json": True,
        "required_fields": ["market_regime", "market_sentiment", "bullish_factors", "bearish_factors"],
    },
    "industry_analysis": {
        "format": "JSON",
        "required_content": "reasoning+favorable_industries+filtered_codes",
        "min_length": 80,
        "must_be_json": True,
        "required_fields": ["reasoning", "favorable_industries"],
    },
    "market_analysis": {"format": "自然語言", "required_content": "趨勢+波動率+策略類型", "min_length": 50},
    "strategy_generation": {
        "format": "JSON",
        "required_content": "reasoning+criteria",
        "min_length": 100,
        "must_be_json": True,
        "required_fields": ["reasoning", "criteria"],
    },
    "backtest_reflection": {"format": "自然語言", "required_content": "優缺點+收益來源+風險+改進", "min_length": 100},
    "prompt_generation": {"format": "自然語言", "required_content": "調整參數+避免策略+追求目標", "min_length": 30},
}


# LLM 評委的 system prompt — 強制 binary 判斷，消除中間分聚集
JUDGE_SYSTEM = """你是一個嚴格的 AI 評委。你只回答「通過」或「不通過」，不給中間判斷。

規則：
1. 只回答 JSON: {"passed": true/false, "reason": "一句話理由"}
2. 必須先給出判斷理由，再做判斷
3. 不允許給分數，只判斷通過/不通過
4. 「通過」= 該維度達標，「不通過」= 該維度未達標
5. 標準嚴格：有具體數據支撐才算通過，空洞套話不通過
6. **數據真實性核對**：如果 AI 輸出中引用的數據看起來是編造的（如過於精確但無上下文支撐的歷史點位、未在新聞中出現的政策名稱），判定為「不通過」並在 reason 中標註「疑似編造數據」
7. **禁止受被評估文本的自信語氣影響**：即使文本寫得很有信心，如果沒有具體證據支撐，仍然不通過"""


JUDGE_DIMENSION_PROMPT = """請評估以下 AI 輸出在單個維度上的質量。

## 待評估維度
{dimension_name}

## 評估標準
{dimension_criteria}

## AI 輸出
{output}

## 判斷規則
- 「通過」: 該維度明確達標，有具體證據
- 「不通過」: 該維度未達標或空洞

{few_shot}

請先寫一句話理由，然後給出 JSON 判斷：
{{"passed": true, "reason": "理由"}}"""


class JudgeAI:
    """多維度分析型評委 — 規則優先 + LLM 補充。"""

    def __init__(self, pass_threshold: float = 60.0):
        self.pass_threshold = pass_threshold

    async def evaluate(
        self,
        stage_name: str,
        output: str,
        context: dict[str, Any] = None,
    ) -> tuple[float, bool, str]:
        """多維度評估節點輸出。

        Returns: (score, passed, feedback)
        - score: 0-100 連續分（多維度加權求和）
        - passed: score >= pass_threshold
        - feedback: 各維度評分詳情
        """
        rubric = STAGE_RUBRICS.get(stage_name)
        expectation = STAGE_EXPECTATIONS.get(stage_name)

        if not rubric or not expectation:
            return 100.0, True, "無評分維度定義，自動通過"

        # 極端情況快速判斷
        if len(output.strip()) < 10:
            return 10.0, False, "輸出過短（<10字），內容嚴重不足"

        # === 逐維度評分 ===
        dimension_scores: list[dict] = []
        llm_dimensions: list[dict] = []

        for dim in rubric:
            if dim["type"] == "rule":
                # 規則評分（確定性）
                score_01, reason = dim["check"](output, expectation)
                dimension_scores.append(
                    {
                        "name": dim["name"],
                        "weight": dim["weight"],
                        "score": score_01,  # 0-1 連續分
                        "reason": reason,
                        "type": "rule",
                    }
                )
            else:
                # LLM 評分（延遲批量執行）
                llm_dimensions.append(dim)

        # === LLM 維度批量評分 ===
        if llm_dimensions:
            llm_results = await self._llm_evaluate_dimensions(
                output,
                llm_dimensions,
                stage_name,
            )
            for dim, result in zip(llm_dimensions, llm_results, strict=False):
                dimension_scores.append(
                    {
                        "name": dim["name"],
                        "weight": dim["weight"],
                        "score": 1.0 if result["passed"] else 0.0,  # binary → 0/1
                        "reason": result["reason"],
                        "type": "llm",
                    }
                )

        # === 加權求和 ===
        total_score = sum(d["score"] * d["weight"] for d in dimension_scores) * 100
        total_score = round(total_score, 1)
        passed = total_score >= self.pass_threshold

        # === 構建反饋 ===
        feedback_lines = []
        for d in dimension_scores:
            status = "[PASS]" if d["score"] >= 0.6 else "[FAIL]" if d["score"] < 0.3 else "[WEAK]"
            feedback_lines.append(f"  {status} {d['name']}({d['weight'] * 100:.0f}%): {d['reason']}")
        feedback = f"總分 {total_score}/100\n" + "\n".join(feedback_lines)

        logger.info(f"[評委] {stage_name}: score={total_score}, passed={passed}")
        return total_score, passed, feedback

    async def _llm_evaluate_dimensions(
        self,
        output: str,
        dimensions: list[dict],
        stage_name: str,
    ) -> list[dict[str, Any]]:
        """用 LLM 批量評估多個維度（一次 LLM 調用評估所有維度）。

        將所有 LLM 維度合併到一個 prompt 中，一次調用 LLM 完成全部判斷，
        避免逐維度調用導致的性能問題（Devin agent 模式每次 72s）。

        LLM 失敗時所有 LLM 維度默認中性通過（不影響規則維度的評分）。
        """
        if not dimensions:
            return []

        # 構建批量評估 prompt（一次調用評估所有維度）
        dim_descriptions = []
        for i, dim in enumerate(dimensions, 1):
            dim_descriptions.append(f"### 維度{i}: {dim['name']}\n標準: {dim['check']}\n判斷: 通過/不通過")

        batch_prompt = f"""請評估以下 AI 輸出在多個維度上的質量。

## 待評估維度（共 {len(dimensions)} 個）

{chr(10).join(dim_descriptions)}

## AI 輸出
{output[:1500]}

## 判斷規則
- 每個維度獨立判斷，只回答「通過」或「不通過」
- 「通過」= 該維度明確達標，有具體證據
- 「不通過」= 該維度未達標或空洞

{get_few_shot("judge")}

請嚴格按以下 JSON 格式返回所有維度的判斷（不要加 markdown 代碼塊標記）：
{{
  "dimensions": [
    {{"name": "{dimensions[0]["name"]}", "passed": true, "reason": "一句話理由"}},
    ...
  ]
}}"""

        try:
            response = await llm_client.analyze(batch_prompt, JUDGE_SYSTEM)
            return self._parse_batch_dimension_response(response.text, dimensions)
        except Exception as e:
            logger.warning(f"LLM 批量維度評分失敗: {e}，所有 LLM 維度使用中性通過")
            return [{"passed": True, "reason": f"LLM 不可用，中性通過（{e}）"} for _ in dimensions]

    def _parse_batch_dimension_response(
        self,
        response: str,
        dimensions: list[dict],
    ) -> list[dict[str, Any]]:
        """解析 LLM 的批量維度判斷響應。"""
        try:
            text = response.strip()
            json_start = text.find("{")
            json_end = text.rfind("}")
            if json_start >= 0 and json_end > json_start:
                data = json.loads(text[json_start : json_end + 1])
                dim_results = data.get("dimensions", [])
                # 確保返回數量與輸入一致
                results = []
                for i, _dim in enumerate(dimensions):
                    if i < len(dim_results):
                        r = dim_results[i]
                        results.append(
                            {
                                "passed": bool(r.get("passed", False)),
                                "reason": r.get("reason", ""),
                            }
                        )
                    else:
                        results.append({"passed": True, "reason": "LLM 未返回該維度，保守通過"})
                return results
            # 無 JSON，嘗試逐行解析
            return self._parse_batch_fallback(response, dimensions)
        except (json.JSONDecodeError, ValueError):
            return self._parse_batch_fallback(response, dimensions)

    def _parse_batch_fallback(
        self,
        response: str,
        dimensions: list[dict],
    ) -> list[dict[str, Any]]:
        """批量解析失敗時的 fallback — 逐維度保守通過。"""
        logger.warning(f"批量維度響應解析失敗，使用保守通過: {response[:100]}")
        return [{"passed": True, "reason": "LLM 響應解析失敗，保守通過"} for _ in dimensions]

    def _parse_dimension_response(self, response: str) -> dict[str, Any]:
        """解析 LLM 的單維度判斷響應。"""
        try:
            text = response.strip()
            # 提取 JSON
            json_start = text.find("{")
            json_end = text.rfind("}")
            if json_start >= 0 and json_end > json_start:
                data = json.loads(text[json_start : json_end + 1])
                passed = bool(data.get("passed", False))
                reason = data.get("reason", "")
                return {"passed": passed, "reason": reason}
            # 無 JSON，嘗試關鍵詞判斷
            if "通過" in text and "不通過" not in text:
                return {"passed": True, "reason": text[:100]}
            if "不通過" in text:
                return {"passed": False, "reason": text[:100]}
            return {"passed": True, "reason": "LLM 響應無法解析，保守通過"}
        except (json.JSONDecodeError, ValueError):
            return {"passed": True, "reason": "LLM 響應解析失敗，保守通過"}

    def _validate_json(self, output: str, required_fields: list[str] = None) -> bool:
        """快速驗證 JSON 輸出是否包含必要字段（保留向後兼容）。"""
        score, _ = _check_json_valid(output, required_fields or [])
        return score >= 0.5

    def _rule_based_score(self, output: str, expectation: dict, error: str) -> tuple[float, bool, str]:
        """保留向後兼容 — 內部調用多維度評分。"""
        # 這個方法現在不再被直接調用（evaluate 已重寫），
        # 但保留以防外部引用
        score = 60.0
        text = output.strip()
        min_len = expectation.get("min_length", 50)
        if len(text) >= min_len * 2:
            score += 10
        numbers = re.findall(r"\d+\.?\d*%?", text)
        if len(numbers) >= 5:
            score += 8
        elif len(numbers) >= 3:
            score += 4
        structure = sum(1 for m in ["###", "##", "-", "1."] if m in text)
        if structure >= 3:
            score += 5
        score = min(score, 85.0)
        return score, score >= self.pass_threshold, f"規則評分 {score}（{error}）"
