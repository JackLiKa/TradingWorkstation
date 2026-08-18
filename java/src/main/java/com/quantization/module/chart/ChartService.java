package com.quantization.module.chart;

import com.quantization.config.properties.AppProperties;
import com.quantization.module.chart.dto.CandlestickDto;
import com.quantization.module.indicator.IndicatorConfig;
import com.quantization.module.indicator.IndicatorEngine;
import com.quantization.module.indicator.IndicatorSeries;
import com.quantization.module.indicator.dto.IndicatorSeriesDto;
import com.quantization.module.stock.StockDaily;
import com.quantization.module.stock.StockDailyQuery;
import com.quantization.module.stock.StockService;
import com.quantization.module.stock.dto.StockDailyDto;
import com.quantization.module.stock.dto.StockDailyQueryDto;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;

/**
 * K线图服务，加载初始批次和更早历史批次的 K线数据，并计算技术指标序列。
 */
@Service
@Transactional(readOnly = true)
public class ChartService {

    public static final int INITIAL_CHART_BATCH = 120;
    public static final int HISTORY_BATCH = 120;

    private final StockService stockService;
    private final IndicatorEngine indicatorEngine;
    private final AppProperties properties;

    public ChartService(StockService stockService, IndicatorEngine indicatorEngine, AppProperties properties) {
        this.stockService = stockService;
        this.indicatorEngine = indicatorEngine;
        this.properties = properties;
    }

    /**
     * 加载 K线初始批次：取最近 {@link #INITIAL_CHART_BATCH} 根 K线并计算指标序列。
     *
     * @param code       股票代码
     * @param adjustflag 复权方式
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @return K线数据 DTO（含 hasMore 标志和指标序列）
     */
    public CandlestickDto loadCandlestick(String code, int adjustflag, LocalDate startDate, LocalDate endDate) {
        StockDailyQueryDto dto = new StockDailyQueryDto(code, adjustflag, startDate, endDate, INITIAL_CHART_BATCH, 0);
        List<StockDaily> records = stockService.domainCandlestick(dto, INITIAL_CHART_BATCH);
        boolean hasMore = chartHasMore(records, startDate);
        IndicatorSeries series = indicatorEngine.buildSeries(records, IndicatorConfig.defaults());
        return new CandlestickDto(code, toDtos(records), hasMore, IndicatorSeriesDto.from(series));
    }

    /**
     * 加载更早历史批次：取 beforeDate 之前 {@link #HISTORY_BATCH} 根 K线并计算指标序列。
     *
     * @param code       股票代码
     * @param adjustflag 复权方式
     * @param beforeDate 截止日期
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @return K线数据 DTO
     */
    public CandlestickDto loadOlder(String code, int adjustflag, LocalDate beforeDate, LocalDate startDate, LocalDate endDate) {
        StockDailyQueryDto dto = new StockDailyQueryDto(code, adjustflag, startDate, endDate, HISTORY_BATCH, 0);
        List<StockDaily> records = stockService.domainOlderCandlestick(dto, beforeDate, HISTORY_BATCH);
        boolean hasMore = !records.isEmpty() && chartHasMore(records, startDate);
        IndicatorSeries series = indicatorEngine.buildSeries(records, IndicatorConfig.defaults());
        return new CandlestickDto(code, toDtos(records), hasMore, IndicatorSeriesDto.from(series));
    }

    private boolean chartHasMore(List<StockDaily> records, LocalDate startDate) {
        if (records == null || records.size() < INITIAL_CHART_BATCH) return false;
        LocalDate earliest = records.get(0).tradeDate();
        if (startDate != null && !earliest.isAfter(startDate)) return false;
        return true;
    }

    private List<StockDailyDto> toDtos(List<StockDaily> records) {
        return records.stream().map(r -> new StockDailyDto(
                r.code(), r.tradeDate(), r.openPrice(), r.highPrice(), r.lowPrice(), r.closePrice(),
                r.preclosePrice(), r.volume(), r.amount(), r.adjustflag(), r.turn(), r.tradeStatus(),
                r.pctChange(), r.isSt())).toList();
    }

    /**
     * 构建默认查询参数（基于应用配置的回看天数和条数限制）。
     *
     * @return 默认查询参数
     */
    public StockDailyQuery defaultQuery() {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusDays(properties.getQueryDefaults().getLookbackDays());
        return new StockDailyQuery("", properties.getQueryDefaults().getAdjustflag(), start, end,
                properties.getQueryDefaults().getLimit(), 0);
    }
}
