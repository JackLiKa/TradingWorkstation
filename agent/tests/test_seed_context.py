"""測試種子上下文（seed context）冷啟動機制。

覆蓋：
- get_seed_context 在不同 iteration 的返回值
- SEED_CONTEXT 包含關鍵內容（默認策略模板、行業輪動、改進方向）
- 種子上下文明確標註「非真實歷史數據」（不違反憲章數據真實性原則）
- base.py get_full_system_prompt 正確注入種子上下文
"""

from app.agents.seed_context import SEED_CONTEXT, SEED_CONTEXT_LITE, get_seed_context


class TestGetSeedContext:
    """測試 get_seed_context 在不同 iteration 的返回值。"""

    def test_full_seed_context_for_first_three_iterations(self):
        """iteration <= 3 時應返回完整 SEED_CONTEXT。"""
        for i in (1, 2, 3):
            result = get_seed_context(i)
            assert result == SEED_CONTEXT, f"iteration={i} 應返回完整 SEED_CONTEXT"

    def test_lite_seed_context_for_iterations_4_to_6(self):
        """iteration 4-6 時應返回精簡版 SEED_CONTEXT_LITE。"""
        for i in (4, 5, 6):
            result = get_seed_context(i)
            assert result == SEED_CONTEXT_LITE, f"iteration={i} 應返回精簡版 SEED_CONTEXT_LITE"

    def test_empty_for_iterations_after_6(self):
        """iteration > 6 時應返回空字符串（已有足夠歷史數據）。"""
        for i in (7, 8, 10, 20, 100):
            result = get_seed_context(i)
            assert result == "", f"iteration={i} 應返回空字符串"

    def test_full_is_longer_than_lite(self):
        """完整版應比精簡版長。"""
        assert len(SEED_CONTEXT) > len(SEED_CONTEXT_LITE)

    def test_lite_is_not_empty(self):
        """精簡版不應為空。"""
        assert len(SEED_CONTEXT_LITE) > 50


class TestSeedContextContent:
    """測試 SEED_CONTEXT 內容包含關鍵信息。"""

    def test_contains_default_strategy_template(self):
        """應包含默認策略模板。"""
        assert "默認策略模板" in SEED_CONTEXT
        assert "漲跌幅" in SEED_CONTEXT
        assert "換手率" in SEED_CONTEXT
        assert "量比" in SEED_CONTEXT

    def test_contains_industry_rotation_rules(self):
        """應包含 A 股行業輪動基本規律。"""
        assert "行業輪動" in SEED_CONTEXT
        assert "科技" in SEED_CONTEXT
        assert "金融" in SEED_CONTEXT
        assert "消費" in SEED_CONTEXT
        assert "周期" in SEED_CONTEXT

    def test_contains_improvement_directions(self):
        """應包含常見策略改進方向。"""
        assert "改進方向" in SEED_CONTEXT
        assert "動量" in SEED_CONTEXT
        assert "均值回歸" in SEED_CONTEXT
        assert "量價配合" in SEED_CONTEXT

    def test_contains_backtest_params(self):
        """應包含回測參數。"""
        assert "持有期" in SEED_CONTEXT
        assert "調倉間隔" in SEED_CONTEXT
        assert "最大持倉" in SEED_CONTEXT
        assert "初始資金" in SEED_CONTEXT

    def test_marks_as_not_real_data(self):
        """種子上下文必須明確標註「非真實歷史數據」（不違反憲章數據真實性原則）。"""
        assert "非真實歷史數據" in SEED_CONTEXT
        assert "非當前市場數據" in SEED_CONTEXT
        assert "通用常識" in SEED_CONTEXT

    def test_lite_also_marks_as_not_real_data(self):
        """精簡版也必須標註「非真實歷史數據」。"""
        assert "非真實歷史數據" in SEED_CONTEXT_LITE
        assert "非當前市場數據" in SEED_CONTEXT_LITE


class TestSeedContextIntegration:
    """測試種子上下文集成到 base.py get_full_system_prompt。"""

    def test_full_system_prompt_contains_seed_for_iteration_1(self):
        """iteration=1 時 get_full_system_prompt 應包含種子上下文。"""
        from app.agents.stages.base import BaseStage

        # 創建一個具體子類用於測試（BaseStage 是抽象類）
        class _TestStage(BaseStage):
            async def execute(self, **kwargs):
                return ""

            def get_system_prompt(self):
                return "測試節點職責"

        stage = _TestStage("test", "Test")
        prompt = stage.get_full_system_prompt(iteration=1)
        assert "種子上下文" in prompt
        assert "默認策略模板" in prompt

    def test_full_system_prompt_contains_lite_seed_for_iteration_5(self):
        """iteration=5 時 get_full_system_prompt 應包含精簡版種子上下文。"""
        from app.agents.stages.base import BaseStage

        class _TestStage(BaseStage):
            async def execute(self, **kwargs):
                return ""

            def get_system_prompt(self):
                return "測試節點職責"

        stage = _TestStage("test", "Test")
        prompt = stage.get_full_system_prompt(iteration=5)
        assert "種子上下文精簡版" in prompt

    def test_full_system_prompt_no_seed_for_iteration_7(self):
        """iteration=7 時 get_full_system_prompt 不應包含種子上下文。"""
        from app.agents.stages.base import BaseStage

        class _TestStage(BaseStage):
            async def execute(self, **kwargs):
                return ""

            def get_system_prompt(self):
                return "測試節點職責"

        stage = _TestStage("test", "Test")
        prompt = stage.get_full_system_prompt(iteration=7)
        assert "種子上下文" not in prompt

    def test_seed_injected_after_charter_before_node_role(self):
        """種子上下文應在憲章後、節點職責前注入。"""
        from app.agents.stages.base import BaseStage

        class _TestStage(BaseStage):
            async def execute(self, **kwargs):
                return ""

            def get_system_prompt(self):
                return "本節點職責XYZ"

        stage = _TestStage("test", "Test")
        prompt = stage.get_full_system_prompt(iteration=1)
        charter_pos = prompt.find("Agent 憲章")
        seed_pos = prompt.find("種子上下文")
        role_pos = prompt.find("本節點職責XYZ")
        assert charter_pos < seed_pos < role_pos, "種子上下文應在憲章後、節點職責前"
