"""測試評委 AI — 多維度評分系統。"""

import asyncio
import json

import pytest

from app.agents.judge import (
    STAGE_EXPECTATIONS,
    STAGE_RUBRICS,
    JudgeAI,
    _check_data_density,
    _check_json_valid,
    _check_length,
    _check_required_keywords,
    _check_structure,
)


class TestRuleChecks:
    """測試規則維度評分函數。"""

    def test_check_length_sufficient(self):
        score, reason = _check_length("a" * 200, 100)
        assert score == 1.0
        assert "200" in reason

    def test_check_length_insufficient(self):
        score, reason = _check_length("short", 100)
        assert score < 0.5
        assert "5/100" in reason

    def test_check_json_valid_complete(self):
        output = '{"reasoning": "test", "criteria": {"minTurn": 1.5}}'
        score, reason = _check_json_valid(output, ["reasoning", "criteria"])
        assert score == 1.0

    def test_check_json_valid_missing_fields(self):
        output = '{"reasoning": "test"}'
        score, reason = _check_json_valid(output, ["reasoning", "criteria"])
        assert score == 0.5
        assert "criteria" in reason

    def test_check_json_invalid(self):
        output = "not json at all"
        score, reason = _check_json_valid(output, [])
        assert score == 0.0

    def test_check_json_with_markdown(self):
        output = '```json\n{"reasoning": "test", "criteria": {}}\n```'
        score, reason = _check_json_valid(output, ["reasoning", "criteria"])
        assert score == 1.0

    def test_check_data_density_high(self):
        text = "漲幅2.8%，跌幅0.5%，換手率1.5%，量比1.2%，夏普1.05"
        score, reason = _check_data_density(text)
        assert score == 1.0
        assert "5" in reason

    def test_check_data_density_low(self):
        text = "市場不錯可以關注"
        score, reason = _check_data_density(text)
        assert score <= 0.5

    def test_check_structure_rich(self):
        text = "### 標題1\n- 項目1\n### 標題2\n1. 編號1\n2. 編號2"
        score, reason = _check_structure(text)
        assert score == 1.0

    def test_check_structure_poor(self):
        text = "這是一段沒有任何結構標記的純文本內容"
        score, reason = _check_structure(text)
        assert score <= 0.4

    def test_check_required_keywords_all_present(self):
        text = "市場情緒偏多，利好半導體，利空房地產，選股建議關注龍頭"
        score, reason = _check_required_keywords(text, ["市場情緒", "利好", "利空", "選股"])
        assert score == 1.0

    def test_check_required_keywords_partial(self):
        text = "市場情緒偏多，利好半導體"
        score, reason = _check_required_keywords(text, ["市場情緒", "利好", "利空", "選股"])
        # 2/4 = 0.5 ratio → 0.6 score (>= 0.5 ratio branch)
        assert score == 0.6
        assert "利空" in reason
        assert "選股" in reason


class TestJudgeEvaluation:
    """測試評委整體評估。"""

    @pytest.fixture
    def judge(self):
        return JudgeAI(pass_threshold=60.0)

    def test_unknown_stage_auto_pass(self, judge):
        """未知階段自動通過。"""
        score, passed, feedback = asyncio.run(judge.evaluate("unknown_stage", "test"))
        assert score == 100.0
        assert passed is True

    def test_extremely_short_output(self, judge):
        """極短輸出直接低分。"""
        score, passed, feedback = asyncio.run(judge.evaluate("market_news", "短"))
        assert score == 10.0
        assert passed is False

    def test_high_quality_market_news(self, judge):
        """高質量 market_news 應該高分（含市場形態識別）。"""
        output = """### 市場形態
最近10日漲跌交替6次，交替率67%，平均幅度0.8%，呈現震盪行情。

### 市場情緒
上證指數上漲0.85%，深證成指上漲1.23%，市場情緒偏多。

### 利好行業
1. 半導體：板塊漲幅2.8%，受益國產替代政策
2. 新能源：板塊漲幅2.1%，鋰電漲價預期

### 利空行業
1. 房地產：板塊跌幅0.8%，銷售低迷

### 選股建議
關注半導體和新能源龍頭股。"""
        score, passed, feedback = asyncio.run(judge.evaluate("market_news", output))
        assert score > 70, f"高質量輸出應 >70，得到 {score}"
        assert passed is True

    def test_low_quality_market_news(self, judge):
        """低質量 market_news 應該低分。"""
        score, passed, feedback = asyncio.run(judge.evaluate("market_news", "市場還不錯"))
        assert score < 50, f"低質量應 <50，得到 {score}"
        assert passed is False

    def test_valid_strategy_json(self, judge):
        """有效 strategy JSON 應該通過。"""
        output = json.dumps(
            {
                "reasoning": "市場震盪上行，新增換手率下限1.5%篩選活躍股",
                "criteria": {"minTurn": 1.5, "minReturn20": 3.0},
            }
        )
        score, passed, feedback = asyncio.run(judge.evaluate("strategy_generation", output))
        assert score > 50, f"有效 JSON 應 >50，得到 {score}"

    def test_invalid_strategy_json(self, judge):
        """無效 strategy JSON 應該低分。"""
        score, passed, feedback = asyncio.run(judge.evaluate("strategy_generation", "我建議調整一些參數"))
        assert score < 40, f"無效 JSON 應 <40，得到 {score}"
        assert passed is False

    def test_score_not_fixed_70(self, judge):
        """分數不應該固定在 70。"""
        scores = []
        outputs = [
            ("market_news", "市場好"),  # 極差
            (
                "market_news",
                "### 市場情緒\n上證上漲0.85%\n### 利好\n半導體漲2.8%\n### 利空\n房地產跌0.8%\n### 選股\n關注半導體",
            ),  # 中等
        ]
        for stage, output in outputs:
            s, _, _ = asyncio.run(judge.evaluate(stage, output))
            scores.append(s)
        # 兩個不同質量的輸入不應該得到相同分數
        assert scores[0] != scores[1], f"分數無區分度: {scores}"

    def test_feedback_contains_dimensions(self, judge):
        """反饋應該包含各維度評分詳情。"""
        # 用中等長度輸入觸發維度評分（非極短快速判斷）
        score, passed, feedback = asyncio.run(
            judge.evaluate("market_news", "市場情緒偏多，利好半導體，利空房地產，選股建議關注龍頭股，漲幅2.8%")
        )
        assert "總分" in feedback
        assert "長度" in feedback or "數據" in feedback or "結構" in feedback

    def test_rubric_definitions_complete(self):
        """所有階段都應該有 rubric 定義。"""
        for stage_name in STAGE_EXPECTATIONS:
            assert stage_name in STAGE_RUBRICS, f"{stage_name} 缺少 rubric 定義"
            rubric = STAGE_RUBRICS[stage_name]
            # 每個 rubric 至少 3 個維度
            assert len(rubric) >= 3, f"{stage_name} rubric 維度不足"
            # 權重總和應該接近 1.0
            total_weight = sum(d["weight"] for d in rubric)
            assert abs(total_weight - 1.0) < 0.01, f"{stage_name} 權重和={total_weight} ≠ 1.0"
            # 每個維度有 name/weight/type/check
            for dim in rubric:
                assert "name" in dim
                assert "weight" in dim
                assert dim["type"] in ("rule", "llm")
                assert "check" in dim
