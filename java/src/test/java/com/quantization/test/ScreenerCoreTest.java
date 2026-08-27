package com.quantization.test;

import com.quantization.module.indicator.IndicatorEngine;
import com.quantization.module.screener.ScreenerCore;
import com.quantization.module.screener.dto.ScreenedStockDto;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import com.quantization.module.stock.StockDaily;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * ScreenerCore 集成测试 — 验证选股分组、筛选、排序逻辑。
 * 移植 Python test_run_stock_screener_supports_ranges_and_technical_filters 场景。
 */
@DisplayName("ScreenerCore 选股逻辑")
class ScreenerCoreTest {

    private final ScreenerCore screenerCore = new ScreenerCore(new IndicatorEngine());

    @Test
    @DisplayName("4 只股票分组后 histories 包含 4 个 code")
    void groupHistoriesProduces4Codes() {
        ScreenerCore.Grouped grouped = screenerCore.groupHistories(TestDataBuilder.allRecords());
        assertThat(grouped.histories()).hasSize(4);
        assertThat(grouped.histories()).containsKeys("sh.600000", "sz.000001", "sh.600010", "sz.000777");
        assertThat(grouped.histories().get("sh.600000")).hasSize(180);
        List<LocalDate> dates = grouped.dates().get("sh.600000");
        assertThat(dates.get(0)).isEqualTo(LocalDate.of(2026, 1, 2));
        assertThat(dates.get(179)).isEqualTo(LocalDate.of(2026, 6, 30));
    }

    @Test
    @DisplayName("严格条件筛选：仅强势股 sh.600000 命中（移植 Python test_run_stock_screener_supports_ranges_and_technical_filters）")
    void strictScreenerMatchesOnlyStrongStock() {
        ScreenerCore.Grouped grouped = screenerCore.groupHistories(TestDataBuilder.allRecords());
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .minPctChange(0.5)
                .minTurn(5.0)
                .minAmplitude(3.5)
                .minVolumeRatio(1.02)
                .minReturn20(10.0)
                .minReturn60(50.0)
                .minReturn120(100.0)
                .minRsi14(80.0)
                .minBollWidth(10.0)
                .minBollPercentB(80.0)
                .kdjCrossSignal("golden_cross")
                .bollPosition("upper_zone")
                .excludeSt(true)
                .maxResults(20)
                .sortBy("score")
                .build();
        List<ScreenedStockDto> candidates = screenerCore.screenAt(grouped, TestDataBuilder.SCREEN_DATE, criteria, 20);

        assertThat(candidates).hasSize(1);
        assertThat(candidates.get(0).code()).isEqualTo("sh.600000");
        assertThat(candidates.get(0).kdjCrossSignal()).isEqualTo("golden_cross");
        assertThat(candidates.get(0).bollPosition()).isEqualTo("upper_zone");
        assertThat(candidates.get(0).macdHist()).isNotNull();
        assertThat(candidates.get(0).bollWidth()).isNotNull();
    }

    @Test
    @DisplayName("弱势股筛选：maxPctChange=1.0 + MACD 金叉 + BOLL 下轨区域 → sh.600010 命中")
    void weakStockScreenerMatchesSh600010() {
        ScreenerCore.Grouped grouped = screenerCore.groupHistories(TestDataBuilder.allRecords());
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .maxPctChange(1.0)
                .macdCrossSignal("golden_cross")
                .bollPosition("lower_zone")
                .excludeSt(true)
                .maxResults(10)
                .sortBy("score")
                .build();
        List<ScreenedStockDto> candidates = screenerCore.screenAt(grouped, TestDataBuilder.SCREEN_DATE, criteria, 10);

        assertThat(candidates).hasSize(1);
        assertThat(candidates.get(0).code()).isEqualTo("sh.600010");
        assertThat(candidates.get(0).macdCrossSignal()).isEqualTo("golden_cross");
        assertThat(candidates.get(0).bollPosition()).isEqualTo("lower_zone");
    }

    @Test
    @DisplayName("excludeSt=true 时 ST 股 sz.000777 被排除")
    void stStockExcludedWhenExcludeStTrue() {
        ScreenerCore.Grouped grouped = screenerCore.groupHistories(TestDataBuilder.allRecords());
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .excludeSt(true)
                .maxResults(100)
                .build();
        List<ScreenedStockDto> candidates = screenerCore.screenAt(grouped, TestDataBuilder.SCREEN_DATE, criteria, 100);
        assertThat(candidates).hasSize(3);
        assertThat(candidates).noneMatch(c -> c.code().equals("sz.000777"));
    }

    @Test
    @DisplayName("按 score 排序：评分降序")
    void sortByScoreDescending() {
        ScreenerCore.Grouped grouped = screenerCore.groupHistories(TestDataBuilder.allRecords());
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .excludeSt(true)
                .maxResults(100)
                .sortBy("score")
                .build();
        List<ScreenedStockDto> candidates = screenerCore.screenAt(grouped, TestDataBuilder.SCREEN_DATE, criteria, 100);
        assertThat(candidates).isNotEmpty();
        for (int i = 1; i < candidates.size(); i++) {
            assertThat(candidates.get(0).score()).isGreaterThanOrEqualTo(candidates.get(i).score());
        }
    }

    @Test
    @DisplayName("maxResults 限制返回数量")
    void maxResultsLimitsOutput() {
        ScreenerCore.Grouped grouped = screenerCore.groupHistories(TestDataBuilder.allRecords());
        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .excludeSt(true)
                .maxResults(2)
                .build();
        List<ScreenedStockDto> candidates = screenerCore.screenAt(grouped, TestDataBuilder.SCREEN_DATE, criteria, 2);
        assertThat(candidates).hasSizeLessThanOrEqualTo(2);
    }
}
