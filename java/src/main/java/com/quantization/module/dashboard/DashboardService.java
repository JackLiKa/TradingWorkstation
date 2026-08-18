package com.quantization.module.dashboard;

import com.quantization.common.util.FormatUtils;
import com.quantization.config.properties.AppProperties;
import com.quantization.module.chart.ChartService;
import com.quantization.module.chart.dto.CandlestickDto;
import com.quantization.module.dashboard.dto.DashboardMetricDto;
import com.quantization.module.dashboard.dto.DashboardSnapshotDto;
import com.quantization.module.stock.StockDaily;
import com.quantization.module.stock.StockDailyQuery;
import com.quantization.module.stock.StockService;
import com.quantization.module.stock.dto.HotSymbolDto;
import com.quantization.module.stock.dto.StockDailyDto;
import com.quantization.module.stock.dto.StockDailyQueryDto;
import com.quantization.module.stock.dto.SummaryMetricsDto;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * 仪表盘服务，并行加载指标卡片、行情表格、K线图、波动榜等资源，
 * 汇聚为统一的仪表盘快照。
 */
@Service
@Transactional(readOnly = true)
public class DashboardService {

    private final StockService stockService;
    private final ChartService chartService;
    private final AppProperties properties;
    private final Executor asyncExecutor;

    public DashboardService(StockService stockService, ChartService chartService, AppProperties properties, Executor asyncExecutor) {
        this.stockService = stockService;
        this.chartService = chartService;
        this.properties = properties;
        this.asyncExecutor = asyncExecutor;
    }

    /**
     * 加载仪表盘快照：并行加载数据库连接状态、汇总指标、行情表格、波动榜和 K线图。
     *
     * @param code       股票代码（可选）
     * @param adjustflag 复权方式（可选）
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @param limit      返回条数限制（可选）
     * @return 仪表盘快照 DTO
     */
    public DashboardSnapshotDto loadDashboard(String code, Integer adjustflag, LocalDate startDate, LocalDate endDate, Integer limit) {
        StockDailyQueryDto queryDto = buildQueryDto(code, adjustflag, startDate, endDate, limit);

        // 並行加載獨立資源（summary 走緩存，movers 和 search 獨立查詢）
        CompletableFuture<Boolean> connectedFuture = CompletableFuture.supplyAsync(stockService::ping, asyncExecutor);
        CompletableFuture<SummaryMetricsDto> summaryFuture = CompletableFuture.supplyAsync(stockService::summaryMetrics, asyncExecutor);
        CompletableFuture<List<StockDailyDto>> recordsFuture = CompletableFuture.supplyAsync(() -> stockService.searchDaily(queryDto), asyncExecutor);
        CompletableFuture<List<HotSymbolDto>> moversFuture = CompletableFuture.supplyAsync(() -> stockService.latestMovers(8), asyncExecutor);

        // 等待 search 完成後解析 chart code（chart 依賴 search 結果）
        CompletableFuture<CandlestickDto> chartFuture = recordsFuture.thenApplyAsync(records -> {
            String chartCode = resolveChartCode(queryDto.code(), records);
            return chartCode.isEmpty()
                    ? new CandlestickDto("", List.of(), false, null)
                    : chartService.loadCandlestick(chartCode, queryDto.adjustflag(), queryDto.startDate(), queryDto.endDate());
        }, asyncExecutor);

        // 匯聚所有結果
        CompletableFuture.allOf(connectedFuture, summaryFuture, recordsFuture, moversFuture, chartFuture).join();

        boolean connected = connectedFuture.join();
        SummaryMetricsDto summary = summaryFuture.join();
        List<StockDailyDto> records = recordsFuture.join();
        List<HotSymbolDto> hotSymbols = moversFuture.join();
        CandlestickDto chart = chartFuture.join();

        String chartCode = resolveChartCode(queryDto.code(), records);
        List<DashboardMetricDto> metrics = buildMetrics(summary);
        String statusText = connected ? "数据库连接正常，搜索结果已刷新" : "数据库暂不可用";
        List<String> logs = buildLogs(queryDto, records.size(),
                chart.records() == null ? 0 : chart.records().size(), chartCode, connected, chart.hasMore());

        return new DashboardSnapshotDto(metrics, records, chart, hotSymbols, queryDto, connected, statusText, logs);
    }

    /**
     * 获取缓存的汇总指标。
     *
     * @return 汇总指标 DTO
     */
    @Cacheable(value = CacheConfigHolder.SUMMARY_CACHE, key = "'summary'")
    public SummaryMetricsDto cachedSummary() {
        return stockService.summaryMetrics();
    }

    private StockDailyQueryDto buildQueryDto(String code, Integer adjustflag, LocalDate startDate, LocalDate endDate, Integer limit) {
        int adj = adjustflag == null ? properties.getQueryDefaults().getAdjustflag() : adjustflag;
        int lim = limit == null ? properties.getQueryDefaults().getLimit() : limit;
        LocalDate end = endDate == null ? LocalDate.now() : endDate;
        LocalDate start = startDate == null ? end.minusDays(properties.getQueryDefaults().getLookbackDays()) : startDate;
        return new StockDailyQueryDto(code == null ? "" : code, adj, start, end, lim, 0);
    }

    private String resolveChartCode(String requestedCode, List<StockDailyDto> records) {
        String normalized = requestedCode == null ? "" : requestedCode.trim();
        if (normalized.contains(".") && normalized.length() >= 9) return normalized;
        return records.isEmpty() ? "" : records.get(0).code();
    }

    private List<DashboardMetricDto> buildMetrics(SummaryMetricsDto summary) {
        String latestDateText = summary.latestTradeDate() == null ? "暂无数据" : summary.latestTradeDate().toString();
        return List.of(
                new DashboardMetricDto("总记录数", String.format("%,d", summary.totalRecords()), "stock_daily 表总行数"),
                new DashboardMetricDto("股票数量", String.format("%,d", summary.totalSymbols()), "去重证券代码数量"),
                new DashboardMetricDto("最新交易日", latestDateText, "数据库内最新行情日期"),
                new DashboardMetricDto("平均涨跌幅", FormatUtils.formatPercent(summary.averagePctChange()), "最新交易日，不复权口径"),
                new DashboardMetricDto("最新成交额", FormatUtils.formatCurrency(summary.latestTurnover()), "最新交易日，不复权口径")
        );
    }

    private List<String> buildLogs(StockDailyQueryDto query, int rowCount, int chartCount, String chartCode,
                                   boolean connected, boolean hasMore) {
        String rangeText = (query.startDate() != null && query.endDate() != null)
                ? query.startDate() + " ~ " + query.endDate() : "未设置日期区间";
        return List.of(
                "数据库连接：" + (connected ? "正常" : "失败"),
                "搜索条件：code='" + (query.code() == null || query.code().isEmpty() ? "全部" : query.code())
                        + "'，adjustflag=" + query.adjustflag() + "，日期 " + rangeText + "，limit=" + query.limit(),
                "表格结果：" + rowCount + " 条",
                "K线图：" + (chartCode.isEmpty() ? "无可用证券" : chartCode) + "，已加载 " + chartCount
                        + " 根K线，" + (hasMore ? "仍有更早历史数据待同步" : "当前区间已加载完成")
        );
    }

    /**
     * 构建默认查询 DTO（基于应用配置的回看天数和条数限制）。
     *
     * @return 默认查询 DTO
     */
    public StockDailyQueryDto defaultQueryDto() {
        StockDailyQuery q = chartService.defaultQuery();
        return new StockDailyQueryDto(q.code(), q.adjustflag(), q.startDate(), q.endDate(), q.limit(), q.offset());
    }
}

/** 仅用于引用缓存名常量，避免循环依赖。 */
final class CacheConfigHolder {
    static final String SUMMARY_CACHE = com.quantization.config.CacheConfig.SUMMARY_CACHE;
}
