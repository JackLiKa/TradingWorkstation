package com.quantization.test;

import com.quantization.module.indicator.IndicatorSnapshot;
import com.quantization.module.screener.ScreenerFilters;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * ScreenerFilters 单元测试 — 验证条件过滤逻辑与原 Python _candidate_matches_criteria 一致。
 * 移植 Python test_recent_cross_window_allows_non_current_signal_match 场景。
 */
@DisplayName("ScreenerFilters 条件过滤")
class ScreenerFiltersTest {

    /** 构造一个可控的候选快照（与 Python test_recent_cross_window 中的 ScreenedStock 对齐）。 */
    private static IndicatorSnapshot testSnapshot() {
        return new IndicatorSnapshot(
                "sh.600000", LocalDate.of(2026, 6, 20),
                10.0, 1.0, 2.0, 5.0, 1_000_000L, 10_000_000.0,
                9.8, 9.7, 9.5, 9.0, 8.5,
                1.2, 8.0, 15.0, 20.0, 60.0,
                55.0, 50.0, 65.0, "none", 4, 9,
                0.1, 0.08, 0.04, "none", 2, 7,
                10.5, 9.8, 9.1, 14.0, 72.0, "middle_upper",
                88.0, false
        );
    }

    private static IndicatorSnapshot stSnapshot() {
        return new IndicatorSnapshot(
                "sz.000777", LocalDate.of(2026, 6, 20),
                6.0, 0.9, 1.5, 4.0, 600_000L, 3_600_000.0,
                5.9, 5.8, 5.7, 5.5, 5.0,
                1.1, 5.0, 10.0, 15.0, 55.0,
                50.0, 48.0, 54.0, "none", 5, 10,
                0.05, 0.04, 0.02, "none", 3, 8,
                6.5, 5.8, 5.1, 12.0, 60.0, "middle_upper",
                70.0, true
        );
    }

    private static IndicatorSnapshot withClose(double close) {
        IndicatorSnapshot s = testSnapshot();
        return new IndicatorSnapshot(
                s.code(), s.tradeDate(), close,
                s.pctChange(), s.amplitude(), s.turn(), s.volume(), s.amount(),
                s.ma5(), s.ma10(), s.ma20(), s.ma60(), s.ma120(),
                s.volumeRatio(), s.return20(), s.return60(), s.return120(), s.rsi14(),
                s.kValue(), s.dValue(), s.jValue(),
                s.kdjCrossSignal(), s.kdjGoldenCrossDaysAgo(), s.kdjDeathCrossDaysAgo(),
                s.dif(), s.dea(), s.macdHist(),
                s.macdCrossSignal(), s.macdGoldenCrossDaysAgo(), s.macdDeathCrossDaysAgo(),
                s.bollUpper(), s.bollMiddle(), s.bollLower(),
                s.bollWidth(), s.bollPercentB(), s.bollPosition(),
                s.score(), s.isSt()
        );
    }

    @Test
    @DisplayName("无任何过滤条件 → 通过")
    void noFiltersPasses() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .build();
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isTrue();
    }

    @Test
    @DisplayName("excludeSt=true 排除 ST 股")
    void excludeStFiltersStStock() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .excludeSt(true)
                .build();
        assertThat(ScreenerFilters.matches(stSnapshot(), criteria)).isFalse();
    }

    @Test
    @DisplayName("excludeSt=false 不排除 ST 股")
    void excludeStFalseKeepsStStock() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .excludeSt(false)
                .build();
        assertThat(ScreenerFilters.matches(stSnapshot(), criteria)).isTrue();
    }

    @Test
    @DisplayName("MACD 金叉窗口 3 天内匹配（golden_cross_days_ago=2 < 3）→ 通过")
    void macdCrossWindowLooseMatch() {
        // testSnapshot: macdCrossSignal="none", macdGoldenCrossDaysAgo=2
        // withinDays=3 → 2 < 3 → 通过（窗口内匹配）
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .macdCrossSignal("golden_cross")
                .macdCrossWithinDays(3)
                .build();
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isTrue();
    }

    @Test
    @DisplayName("MACD 金叉窗口 2 天内不匹配（golden_cross_days_ago=2 不 < 2）→ 拒绝")
    void macdCrossWindowTightReject() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .macdCrossSignal("golden_cross")
                .macdCrossWithinDays(2)
                .build();
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isFalse();
    }

    @Test
    @DisplayName("priceAboveMa20=true 且 close(10) > ma20(9.5) → 通过")
    void priceAboveMa20PassesWhenAbove() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .priceAboveMa20(true)
                .build();
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isTrue();
    }

    @Test
    @DisplayName("priceAboveMa20=true 且 close(9) < ma20(9.5) → 拒绝")
    void priceAboveMa20RejectsWhenBelow() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .priceAboveMa20(true)
                .build();
        assertThat(ScreenerFilters.matches(withClose(9.0), criteria)).isFalse();
    }

    @Test
    @DisplayName("BOLL 位置过滤不匹配 → 拒绝")
    void bollPositionFilterRejects() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .bollPosition("lower_zone")
                .build();
        // snapshot 的 bollPosition="middle_upper" != "lower_zone"
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isFalse();
    }

    @Test
    @DisplayName("BOLL 位置匹配 → 通过")
    void bollPositionFilterPasses() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .bollPosition("middle_upper")
                .build();
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isTrue();
    }

    @Test
    @DisplayName("minReturn20=5.0，return20=8.0 → 通过")
    void minReturn20Passes() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .minReturn20(5.0)
                .build();
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isTrue();
    }

    @Test
    @DisplayName("minReturn20=100.0，return20=8.0 → 拒绝")
    void minReturn20Rejects() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .minReturn20(100.0)
                .build();
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isFalse();
    }

    @Test
    @DisplayName("minPctChange=0.5，pctChange=1.0 → 通过")
    void minPctChangePasses() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .minPctChange(0.5)
                .build();
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isTrue();
    }

    @Test
    @DisplayName("maxPctChange=0.5，pctChange=1.0 → 拒绝")
    void maxPctChangeRejects() {
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(LocalDate.of(2026, 6, 20))
                .maxPctChange(0.5)
                .build();
        assertThat(ScreenerFilters.matches(testSnapshot(), criteria)).isFalse();
    }
}
