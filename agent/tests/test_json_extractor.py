"""json_extractor 單元測試 — 驗證多級降級 JSON 提取策略。"""

from app.utils.json_extractor import extract_json, extract_json_with_fallback


class TestExtractJson:
    """測試各種 LLM 響應格式的 JSON 提取。"""

    def test_pure_json(self):
        """策略 1：純 JSON 直接解析。"""
        response = '{"reasoning": "test", "criteria": {"minTurn": 1.5}}'
        result = extract_json(response)
        assert result is not None
        assert result["reasoning"] == "test"
        assert result["criteria"]["minTurn"] == 1.5

    def test_json_with_surrounding_text(self):
        """策略 3：JSON 前後有自然語言。"""
        response = '好的，以下是策略：\n{"reasoning": "分析", "criteria": {}}\n以上是建議。'
        result = extract_json(response)
        assert result is not None
        assert result["reasoning"] == "分析"

    def test_json_code_block(self):
        """策略 2：```json 代碼塊。"""
        response = '以下是結果：\n```json\n{"reasoning": "test", "criteria": {}}\n```\n完成。'
        result = extract_json(response)
        assert result is not None
        assert result["reasoning"] == "test"

    def test_json_code_block_no_lang(self):
        """策略 2：``` 代碼塊（無 json 標記）。"""
        response = '結果：\n```\n{"reasoning": "test"}\n```'
        result = extract_json(response)
        assert result is not None
        assert result["reasoning"] == "test"

    def test_nested_json(self):
        """策略 3：嵌套 JSON（棧匹配）。"""
        response = '{"outer": {"inner": "value"}, "list": [1, 2, 3]}'
        result = extract_json(response)
        assert result is not None
        assert result["outer"]["inner"] == "value"
        assert result["list"] == [1, 2, 3]

    def test_trailing_comma_fix(self):
        """策略 5：尾逗號修復。"""
        response = '{"reasoning": "test", "criteria": {"minTurn": 1.5,},}'
        result = extract_json(response)
        assert result is not None
        assert result["reasoning"] == "test"
        assert result["criteria"]["minTurn"] == 1.5

    def test_python_bool_fix(self):
        """策略 5：Python 布爾值修復。"""
        response = '{"flag": True, "other": False, "none_field": None}'
        result = extract_json(response)
        assert result is not None
        assert result["flag"] is True
        assert result["other"] is False
        assert result["none_field"] is None

    def test_single_quotes_fix(self):
        """策略 5：單引號修復。"""
        response = "{'reasoning': 'test', 'value': 123}"
        result = extract_json(response)
        assert result is not None
        assert result["reasoning"] == "test"
        assert result["value"] == 123

    def test_no_json_returns_none(self):
        """無 JSON 結構返回 None。"""
        response = "這是一段純文本，沒有任何 JSON 結構。"
        result = extract_json(response)
        assert result is None

    def test_empty_string(self):
        """空字符串返回 None。"""
        assert extract_json("") is None
        assert extract_json("   ") is None

    def test_multiple_json_picks_valid(self):
        """多個 JSON 候選時提取到有效的 JSON（棧匹配選第一個完整的）。"""
        response = '{"short": 1} 一些文字 {"reasoning": "完整分析", "criteria": {"minTurn": 2.0}}'
        result = extract_json(response)
        assert result is not None
        # 棧匹配策略會找到第一個完整的 { ... }，即 {"short": 1}
        assert "short" in result or "reasoning" in result


class TestExtractJsonWithFallback:
    """測試帶兜底值的 JSON 提取。"""

    def test_success_no_fallback_needed(self):
        """成功提取時不使用兜底值。"""
        response = '{"reasoning": "test"}'
        result = extract_json_with_fallback(response, fallback={"default": True})
        assert result["reasoning"] == "test"
        assert "default" not in result

    def test_failure_uses_fallback(self):
        """提取失敗時使用兜底值。"""
        response = "無 JSON 文本"
        fallback = {"reasoning": "默認推理", "criteria": {}}
        result = extract_json_with_fallback(response, fallback=fallback)
        assert result["reasoning"] == "默認推理"
        assert result["criteria"] == {}

    def test_missing_fields_filled_from_fallback(self):
        """缺失的必要字段從兜底值填充。"""
        response = '{"reasoning": "有推理"}'
        fallback = {"reasoning": "默認", "criteria": {"minTurn": 1.0}}
        result = extract_json_with_fallback(
            response, fallback=fallback, required_fields=["reasoning", "criteria"]
        )
        assert result["reasoning"] == "有推理"  # 保留提取到的值
        assert result["criteria"]["minTurn"] == 1.0  # 從兜底填充

    def test_empty_fallback_default(self):
        """無兜底值時返回空 dict。"""
        response = "無 JSON"
        result = extract_json_with_fallback(response)
        assert result == {}
