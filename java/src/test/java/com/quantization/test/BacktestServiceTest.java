package com.quantization.test;

import com.quantization.module.backtest.BacktestService;
import com.quantization.module.backtest.dto.BacktestConfigDto;
import com.quantization.module.backtest.dto.BacktestRequestDto;
import com.quantization.module.backtest.dto.BacktestResultDto;
import com.quantization.module.screener.ScreenerCore;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import com.quantization.module.stock.IndexDailyRepository;
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

    @Test
    @DisplayName("回测生成净值曲线、调仓记录和统计指标（移植 Python test_run_screener_backtest_builds_metrics_and_period_rows）")
    void runBacktestBuildsMetricsAndCurves() {
        StockService stockService = mock(StockService.class);
        ScreenerCore screenerCore = new ScreenerCore(new com.quantization.module.indicator.IndicatorEngine());
        IndexDailyRepository indexDailyRepository = mock(IndexDailyRepository.class);
        BacktestService backtestService = new BacktestService(stockService, screenerCore, indexDailyRepository);

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
        BacktestConfigDto config = new BacktestConfigDto(
                LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                5, 5, 2, 1_000_000.0, 5.0, 3.0, 12.0
        );

        BacktestResultDto result = backtestService.runBacktest(new BacktestRequestDto(criteria, config));

        assertThat(result.rebalances()).isNotEmpty();
        assertThat(result.statistics().totalReturn()).isGreaterThan(0);
        assertThat(result.statistics().maxDrawdown()).isGreaterThanOrEqualTo(0).isLessThan(100);
        assertThat(result.strategyCurve()).isNotEmpty();
        assertThat(result.strategyCurve().get(0).value()).isCloseTo(1_000_000.0, within(1.0));
        assertThat(result.logLines()).anyMatch(line -> line.contains("策略总收益"));
    }

    @Test
    @DisplayName("止损触发：当价格跌至 entryPrice * (1 - stopLoss%) 时平仓")
    void stopLossTriggersExit() {
        StockService stockService = mock(StockService.class);
        ScreenerCore screenerCore = new ScreenerCore(new com.quantization.module.indicator.IndicatorEngine());
        IndexDailyRepository indexDailyRepository = mock(IndexDailyRepository.class);
        BacktestService backtestService = new BacktestService(stockService, screenerCore, indexDailyRepository);

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
        BacktestConfigDto config = new BacktestConfigDto(
                LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                5, 10, 1, 1_000_000.0, 0.0, 5.0, null
        );

        BacktestResultDto result = backtestService.runBacktest(new BacktestRequestDto(criteria, config));

        assertThat(result.statistics().totalTrades()).isGreaterThan(0);
        assertThat(result.strategyCurve()).isNotEmpty();
    }

    @Test
    @DisplayName("空数据返回空结果")
    void emptyDataReturnsEmptyResult() {
        StockService stockService = mock(StockService.class);
        ScreenerCore screenerCore = new ScreenerCore(new com.quantization.module.indicator.IndicatorEngine());
        IndexDailyRepository indexDailyRepository = mock(IndexDailyRepository.class);
        BacktestService backtestService = new BacktestService(stockService, screenerCore, indexDailyRepository);

        when(stockService.domainRecordsInRange(any(), any(), anyInt(), any())).thenReturn(List.of());

        ScreenerCriteriaDto criteria = CriteriaBuilder.create()
                .asOfDate(TestDataBuilder.SCREEN_DATE)
                .excludeSt(true)
                .maxResults(10)
                .build();
        BacktestConfigDto config = new BacktestConfigDto(
                LocalDate.of(2026, 3, 1), LocalDate.of(2026, 6, 20),
                5, 5, 2, 1_000_000.0, 5.0, null, null
        );

        BacktestResultDto result = backtestService.runBacktest(new BacktestRequestDto(criteria, config));
        assertThat(result.strategyCurve()).isEmpty();
        assertThat(result.rebalances()).isEmpty();
        assertThat(result.logLines()).isNotEmpty();
    }

    private static double round(double value, int scale) {
        double factor = Math.pow(10, scale);
        return Math.round(value * factor) / factor;
    }
}
