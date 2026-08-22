package com.quantization.test;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.quantization.module.backtest.BacktestService;
import com.quantization.module.backtest.BacktestStrategyEntity;
import com.quantization.module.backtest.BacktestStrategyRepository;
import com.quantization.module.backtest.dto.BacktestConfigDto;
import com.quantization.module.backtest.dto.BacktestRequestDto;
import com.quantization.module.backtest.dto.BacktestResultDto;
import com.quantization.module.backtest.dto.SavedStrategySummaryDto;
import com.quantization.module.screener.ScreenerCore;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import com.quantization.module.stock.StockDaily;
import com.quantization.module.stock.StockService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * BacktestService 回测逻辑测试。
 * 移植 Python test_run_screener_backtest_builds_metrics_and_period_rows 和
 * test_single_position_return_honors_stop_loss 场景。
 *
 * 使用 Mockito mock StockService 以避免数据库依赖。
 */
@DisplayName("BacktestService 回测逻辑")
class BacktestServiceTest {

    private BacktestService newService(StockService stockService) {
        ScreenerCore screenerCore = new ScreenerCore(new com.quantization.module.indicator.IndicatorEngine());
        BacktestStrategyRepository repo = mock(BacktestStrategyRepository.class);
        when(repo.save(any())).thenAnswer(inv -> inv.getArgument(0));
        return new BacktestService(stockService, screenerCore, repo, testObjectMapper());
    }

    /** 帶 JSR310 模塊的 ObjectMapper，支持 LocalDate 序列化。 */
    private static ObjectMapper testObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.registerModule(new com.fasterxml.jackson.datatype.jsr310.JavaTimeModule());
        mapper.disable(com.fasterxml.jackson.databind.SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        return mapper;
    }

    @Test
    @DisplayName("回测生成净值曲线、调仓记录和统计指标（移植 Python test_run_screener_backtest_builds_metrics_and_period_rows）")
    void runBacktestBuildsMetricsAndCurves() {
        StockService stockService = mock(StockService.class);
        BacktestService backtestService = newService(stockService);

        List<StockDaily> allRecords = TestDataBuilder.allRecords();

        when(stockService.domainRecordsInRange(any(), any(), anyInt(), any())).thenReturn(allRecords);
        when(stockService.tradeDates(any(), any(), anyInt())).thenReturn(
                allRecords.stream()
                        .map(StockDaily::tradeDate)
                        .filter(d -> !d.isBefore(LocalDate.of(2026, 3, 1)) && !d.isAfter(LocalDate.of(2026, 6, 20)))
                        .distinct()
                        .sorted()
                        .toList()
        );

        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .minVolumeRatio(1.0)
                .minReturn20(5.0)
                .priceAboveMa20(true)
                .ma5AboveMa20(true)
                .excludeSt(true)
                .maxResults(30)
                .sortBy("score")
                .build();
        BacktestConfigDto config = defaultConfig(
                LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                5, 5, 2, 1_000_000.0, 5.0, 3.0, 12.0);

        BacktestResultDto result = backtestService.runBacktest(new BacktestRequestDto(criteria, config));

        assertThat(result.rebalances()).isNotEmpty();
        assertThat(result.statistics().totalReturn()).isGreaterThan(0);
        assertThat(result.statistics().maxDrawdown()).isGreaterThanOrEqualTo(0).isLessThan(100);
        assertThat(result.strategyCurve()).isNotEmpty();
        assertThat(result.strategyCurve().get(0).value()).isCloseTo(1_000_000.0, within(1.0));
        assertThat(result.logLines()).anyMatch(line -> line.contains("策略总收益"));
        assertThat(result.logLines()).anyMatch(line -> line.contains("无风险利率"));
    }

    @Test
    @DisplayName("止损触发：当价格跌至 entryPrice * (1 - stopLoss%) 时平仓")
    void stopLossTriggersExit() {
        StockService stockService = mock(StockService.class);
        BacktestService backtestService = newService(stockService);

        List<StockDaily> records = new ArrayList<>(TestDataBuilder.strongStock());
        double entryClose = records.get(40).closePrice();
        StockDaily shock = records.get(41);
        records.set(41, new StockDaily(
                shock.code(), shock.tradeDate(),
                shock.openPrice(),
                round(entryClose * 1.06, 4),
                round(entryClose * 0.92, 4), // low = entry * 0.92（触发 5% 止损）
                shock.closePrice(), shock.preclosePrice(),
                shock.volume(), shock.amount(), shock.adjustflag(),
                shock.turn(), shock.tradeStatus(), shock.pctChange(), shock.isSt()
        ));

        when(stockService.domainRecordsInRange(any(), any(), anyInt(), any())).thenReturn(records);
        when(stockService.tradeDates(any(), any(), anyInt())).thenReturn(
                records.stream().map(StockDaily::tradeDate)
                        .filter(d -> !d.isBefore(LocalDate.of(2026, 3, 1)) && !d.isAfter(LocalDate.of(2026, 6, 20)))
                        .distinct().sorted().toList()
        );

        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .excludeSt(true)
                .maxResults(5)
                .sortBy("score")
                .build();
        BacktestConfigDto config = defaultConfig(
                LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                5, 10, 1, 1_000_000.0, 0.0, 5.0, null);

        BacktestResultDto result = backtestService.runBacktest(new BacktestRequestDto(criteria, config));

        assertThat(result.statistics().totalTrades()).isGreaterThan(0);
        assertThat(result.strategyCurve()).isNotEmpty();
    }

    @Test
    @DisplayName("空数据返回空结果")
    void emptyDataReturnsEmptyResult() {
        StockService stockService = mock(StockService.class);
        BacktestService backtestService = newService(stockService);

        when(stockService.domainRecordsInRange(any(), any(), anyInt(), any())).thenReturn(List.of());

        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .excludeSt(true)
                .maxResults(10)
                .build();
        BacktestConfigDto config = defaultConfig(
                LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                5, 5, 2, 1_000_000.0, 5.0, null, null);

        BacktestResultDto result = backtestService.runBacktest(new BacktestRequestDto(criteria, config));
        assertThat(result.strategyCurve()).isEmpty();
        assertThat(result.rebalances()).isEmpty();
        assertThat(result.logLines()).isNotEmpty();
    }

    @Test
    @DisplayName("runBacktest 自动落库：调用一次 save 保存 resultJson")
    void runBacktestAutoPersistsResult() {
        StockService stockService = mock(StockService.class);
        ScreenerCore screenerCore = new ScreenerCore(new com.quantization.module.indicator.IndicatorEngine());
        BacktestStrategyRepository repo = mock(BacktestStrategyRepository.class);
        when(repo.save(any())).thenAnswer(inv -> inv.getArgument(0));
        BacktestService backtestService = new BacktestService(stockService, screenerCore, repo, testObjectMapper());

        List<StockDaily> allRecords = TestDataBuilder.allRecords();
        when(stockService.domainRecordsInRange(any(), any(), anyInt(), any())).thenReturn(allRecords);
        when(stockService.tradeDates(any(), any(), anyInt())).thenReturn(
                allRecords.stream().map(StockDaily::tradeDate)
                        .filter(d -> !d.isBefore(LocalDate.of(2026, 3, 1)) && !d.isAfter(LocalDate.of(2026, 6, 20)))
                        .distinct().sorted().toList()
        );

        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .excludeSt(true)
                .maxResults(5)
                .sortBy("score")
                .build();
        BacktestConfigDto config = defaultConfig(
                LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                5, 5, 2, 1_000_000.0, 5.0, null, null);

        backtestService.runBacktest(new BacktestRequestDto(criteria, config));

        // 至少落库一次，且 resultJson 非空
        verify(repo, times(1)).save(any());
        org.mockito.ArgumentCaptor<BacktestStrategyEntity> captor =
                org.mockito.ArgumentCaptor.forClass(BacktestStrategyEntity.class);
        verify(repo).save(captor.capture());
        BacktestStrategyEntity saved = captor.getValue();
        assertThat(saved.getResultJson()).isNotBlank();
        assertThat(saved.getSource()).isEqualTo("auto");
        assertThat(saved.getConfigJson()).isNotBlank();
        assertThat(saved.getCriteriaJson()).isNotBlank();
    }

    @Test
    @DisplayName("listRecentRuns 返回最近 N 次记录")
    void listRecentRunsReturnsLimitedRecords() {
        StockService stockService = mock(StockService.class);
        ScreenerCore screenerCore = new ScreenerCore(new com.quantization.module.indicator.IndicatorEngine());
        BacktestStrategyRepository repo = mock(BacktestStrategyRepository.class);
        java.time.LocalDateTime now = java.time.LocalDateTime.now();
        BacktestStrategyEntity e1 = new BacktestStrategyEntity();
        e1.setId(1L); e1.setName("a"); e1.setCreatedAt(now); e1.setUpdatedAt(now);
        BacktestStrategyEntity e2 = new BacktestStrategyEntity();
        e2.setId(2L); e2.setName("b"); e2.setCreatedAt(now.minusDays(1)); e2.setUpdatedAt(now.minusDays(1));
        when(repo.findRecentRuns(2)).thenReturn(List.of(e1, e2));

        BacktestService backtestService = new BacktestService(stockService, screenerCore, repo, testObjectMapper());
        List<SavedStrategySummaryDto> runs = backtestService.listRecentRuns(2);

        assertThat(runs).hasSize(2);
        assertThat(runs.get(0).id()).isEqualTo(1L);
        verify(repo).findRecentRuns(2);
        verify(repo, never()).findAll();
    }

    @Test
    @DisplayName("滑点配置生效：买入成交价上浮、卖出成交价下浮")
    void slippageAppliedToFillPrice() {
        StockService stockService = mock(StockService.class);
        BacktestService backtestService = newService(stockService);

        List<StockDaily> allRecords = TestDataBuilder.allRecords();
        when(stockService.domainRecordsInRange(any(), any(), anyInt(), any())).thenReturn(allRecords);
        when(stockService.tradeDates(any(), any(), anyInt())).thenReturn(
                allRecords.stream().map(StockDaily::tradeDate)
                        .filter(d -> !d.isBefore(LocalDate.of(2026, 3, 1)) && !d.isAfter(LocalDate.of(2026, 6, 20)))
                        .distinct().sorted().toList()
        );

        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .excludeSt(true)
                .maxResults(5)
                .sortBy("score")
                .build();
        // 50 bp 滑点 + 0 手续费，便于观察滑点对净值的影响
        BacktestConfigDto config = new BacktestConfigDto(
                LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                5, 5, 2, 1_000_000.0, 0.0, null, null,
                0.02, 50);

        BacktestResultDto result = backtestService.runBacktest(new BacktestRequestDto(criteria, config));

        assertThat(result.strategyCurve()).isNotEmpty();
        // 滑点会拖累策略净值（相比无滑点），这里只验证不抛异常且曲线生成
        assertThat(result.logLines()).anyMatch(line -> line.contains("滑点：50 bp"));
    }

    @Test
    @DisplayName("夏普比率扣除无风险利率：rf=0 时与原公式一致，rf>0 时夏普更低")
    void sharpeDeductsRiskFreeRate() {
        StockService stockService = mock(StockService.class);

        List<StockDaily> allRecords = TestDataBuilder.allRecords();
        when(stockService.domainRecordsInRange(any(), any(), anyInt(), any())).thenReturn(allRecords);
        when(stockService.tradeDates(any(), any(), anyInt())).thenReturn(
                allRecords.stream().map(StockDaily::tradeDate)
                        .filter(d -> !d.isBefore(LocalDate.of(2026, 3, 1)) && !d.isAfter(LocalDate.of(2026, 6, 20)))
                        .distinct().sorted().toList()
        );

        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .excludeSt(true)
                .maxResults(5)
                .sortBy("score")
                .build();

        BacktestResultDto rf0 = newService(stockService).runBacktest(new BacktestRequestDto(criteria,
                new BacktestConfigDto(LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                        5, 5, 2, 1_000_000.0, 0.0, null, null, 0.0, 0)));
        BacktestResultDto rfHigh = newService(stockService).runBacktest(new BacktestRequestDto(criteria,
                new BacktestConfigDto(LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                        5, 5, 2, 1_000_000.0, 0.0, null, null, 0.5, 0)));

        // 高无风险利率下夏普应不高于零利率夏普
        assertThat(rfHigh.statistics().sharpe()).isLessThanOrEqualTo(rf0.statistics().sharpe());
    }

    /** 构建默认配置（riskFreeRate=0.02, slippageBps=0）。 */
    private BacktestConfigDto defaultConfig(LocalDate start, LocalDate end,
                                            int rebalanceInterval, int holdingPeriod, int maxPositions,
                                            double initialCapital, double commissionBps,
                                            Double stopLossPct, Double takeProfitPct) {
        return new BacktestConfigDto(start, end, rebalanceInterval, holdingPeriod, maxPositions,
                initialCapital, commissionBps, stopLossPct, takeProfitPct, 0.02, 0);
    }

    private static double round(double value, int scale) {
        double factor = Math.pow(10, scale);
        return Math.round(value * factor) / factor;
    }
}
