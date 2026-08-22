package com.quantization.module.chart;

import com.quantization.config.properties.AppProperties;
import com.quantization.module.chart.dto.CandlestickDto;
import com.quantization.module.indicator.IndicatorConfig;
import com.quantization.module.indicator.IndicatorEngine;
import com.quantization.module.indicator.IndicatorSeries;
import com.quantization.module.indicator.dto.IndicatorConfigDto;
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
 * <p>
 * 批次大小由 {@code app.chart.batch-size} 配置項控制（默認 500），
 * 指標配置可由調用方透傳，未指定時使用 {@link IndicatorConfig#defaults()}。
 * </p>
 */
@Service
@Transactional(readOnly = true)
public class ChartService {

    private final StockService stockService;
    private final IndicatorEngine indicatorEngine;
    private final AppProperties properties;

    public ChartService(StockService stockService, IndicatorEngine indicatorEngine, AppProperties properties) {
        this.stockService = stockService;
        this.indicatorEngine = indicatorEngine;
        this.properties = properties;
    }

    /**
     * 当前配置的 K 线批次大小（来自 {@code app.chart.batch-size}）。
     *
     * @return 批次大小
     */
    public int batchSize() {
        return properties.getChart().getBatchSize();
    }

    /**
     * 加载 K线初始批次：取最近 {@link #batchSize()} 根 K线并计算指标序列。
     *
     * @param code       股票代码
     * @param adjustflag 复权方式
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @return K线数据 DTO（含 hasMore 标志和指标序列）
     */
    public CandlestickDto loadCandlestick(String code, int adjustflag, LocalDate startDate, LocalDate endDate) {
        return loadCandlestick(code, adjustflag, startDate, endDate, null);
    }

    /**
     * 加载 K线初始批次：取最近 {@link #batchSize()} 根 K线并计算指标序列，
     * 支持透传指標配置。
     *
     * @param code       股票代码
     * @param adjustflag 复权方式
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @param configDto  指標配置（可為 null，使用默認值）
     * @return K线数据 DTO（含 hasMore 标志和指标序列）
     */
    public CandlestickDto loadCandlestick(String code, int adjustflag, LocalDate startDate, LocalDate endDate,
                                          IndicatorConfigDto configDto) {
        int batch = batchSize();
        StockDailyQueryDto dto = new StockDailyQueryDto(code, adjustflag, startDate, endDate, batch, 0);
        List<StockDaily> records = stockService.domainCandlestick(dto, batch);
        boolean hasMore = chartHasMore(records, startDate);
        IndicatorConfig config = mergeConfig(configDto, IndicatorConfig.defaults());
        IndicatorSeries series = indicatorEngine.buildSeries(records, config);
        return new CandlestickDto(code, toDtos(records), hasMore, IndicatorSeriesDto.from(series));
    }

    /**
     * 加载更早历史批次：取 beforeDate 之前 {@link #batchSize()} 根 K线并计算指标序列。
     *
     * @param code       股票代码
     * @param adjustflag 复权方式
     * @param beforeDate 截止日期
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @return K线数据 DTO
     */
    public CandlestickDto loadOlder(String code, int adjustflag, LocalDate beforeDate, LocalDate startDate, LocalDate endDate) {
        return loadOlder(code, adjustflag, beforeDate, startDate, endDate, null);
    }

    /**
     * 加载更早历史批次：取 beforeDate 之前 {@link #batchSize()} 根 K线并计算指标序列，
     * 支持透传指標配置。
     *
     * @param code       股票代码
     * @param adjustflag 复权方式
     * @param beforeDate 截止日期
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @param configDto  指標配置（可為 null，使用默認值）
     * @return K线数据 DTO
     */
    public CandlestickDto loadOlder(String code, int adjustflag, LocalDate beforeDate, LocalDate startDate, LocalDate endDate,
                                    IndicatorConfigDto configDto) {
        int batch = batchSize();
        StockDailyQueryDto dto = new StockDailyQueryDto(code, adjustflag, startDate, endDate, batch, 0);
        List<StockDaily> records = stockService.domainOlderCandlestick(dto, beforeDate, batch);
        boolean hasMore = !records.isEmpty() && chartHasMore(records, startDate);
        IndicatorConfig config = mergeConfig(configDto, IndicatorConfig.defaults());
        IndicatorSeries series = indicatorEngine.buildSeries(records, config);
        return new CandlestickDto(code, toDtos(records), hasMore, IndicatorSeriesDto.from(series));
    }

    private boolean chartHasMore(List<StockDaily> records, LocalDate startDate) {
        if (records == null || records.size() < batchSize()) return false;
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

    /** 將請求 DTO 與默認值合併：DTO 中非 null 的字段覆蓋默認值。 */
    private static IndicatorConfig mergeConfig(IndicatorConfigDto dto, IndicatorConfig defaults) {
        if (dto == null) {
            return defaults;
        }
        return new IndicatorConfig(
                dto.showMa() != null ? dto.showMa() : defaults.showMa(),
                dto.maPeriods() != null ? dto.maPeriods() : defaults.maPeriods(),
                dto.showBoll() != null ? dto.showBoll() : defaults.showBoll(),
                dto.showMacd() != null ? dto.showMacd() : defaults.showMacd(),
                dto.showKdj() != null ? dto.showKdj() : defaults.showKdj(),
                dto.bollPeriod() != null ? dto.bollPeriod() : defaults.bollPeriod(),
                dto.bollStd() != null ? dto.bollStd() : defaults.bollStd(),
                dto.macdFastPeriod() != null ? dto.macdFastPeriod() : defaults.macdFastPeriod(),
                dto.macdSlowPeriod() != null ? dto.macdSlowPeriod() : defaults.macdSlowPeriod(),
                dto.macdSignalPeriod() != null ? dto.macdSignalPeriod() : defaults.macdSignalPeriod(),
                dto.kdjPeriod() != null ? dto.kdjPeriod() : defaults.kdjPeriod(),
                dto.kdjKSmoothing() != null ? dto.kdjKSmoothing() : defaults.kdjKSmoothing(),
                dto.kdjDSmoothing() != null ? dto.kdjDSmoothing() : defaults.kdjDSmoothing()
        );
    }
}
