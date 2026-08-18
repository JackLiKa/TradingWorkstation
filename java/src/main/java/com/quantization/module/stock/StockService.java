package com.quantization.module.stock;

import com.quantization.config.CacheConfig;
import com.quantization.module.stock.dto.HotSymbolDto;
import com.quantization.module.stock.dto.SearchResultDto;
import com.quantization.module.stock.dto.StockDailyDto;
import com.quantization.module.stock.dto.StockDailyQueryDto;
import com.quantization.module.stock.dto.StockSuggestionDto;
import com.quantization.module.stock.dto.SummaryMetricsDto;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 行情服务，封装股票日线的查询、汇总、K线加载和搜索建议等业务逻辑。
 * 提供 DTO 和领域对象两种返回形式，供 Controller 和其他模块复用。
 */
@Service
@Transactional(readOnly = true)
public class StockService {

    private final StockDailyRepository repository;

    public StockService(StockDailyRepository repository) {
        this.repository = repository;
    }

    /**
     * 数据库连通性检查。
     *
     * @return true 表示连接正常
     */
    public boolean ping() {
        return repository.ping();
    }

    /**
     * 获取汇总指标（走缓存）。
     *
     * @return 汇总指标 DTO
     */
    @Cacheable(value = CacheConfig.SUMMARY_CACHE, key = "'summary'")
    public SummaryMetricsDto summaryMetrics() {
        StockSummaryProjection p = repository.summaryMetrics();
        return new SummaryMetricsDto(p.totalRecords(), p.totalSymbols(), p.latestTradeDate(),
                p.averagePctChange(), p.latestTurnover());
    }

    /**
     * 日线表格查询，返回 DTO 列表。
     *
     * @param dto 查询参数 DTO
     * @return 日线 DTO 列表
     */
    public List<StockDailyDto> searchDaily(StockDailyQueryDto dto) {
        StockDailyQuery q = dto.toDomain();
        return repository.searchDaily(q).stream().map(StockService::toDto).toList();
    }

    /**
     * 分页搜索：多取 1 条判断 hasMore，避免昂贵的 COUNT 查询。
     *
     * @param dto 查询参数 DTO
     * @return 分页搜索结果
     */
    public SearchResultDto searchDailyPaged(StockDailyQueryDto dto) {
        StockDailyQuery q = dto.toDomain();
        // 多取 1 条用于判断 hasMore
        StockDailyQuery probeQuery = new StockDailyQuery(q.code(), q.adjustflag(), q.startDate(), q.endDate(), q.limit() + 1, q.offset());
        List<StockDailyDto> records = repository.searchDaily(probeQuery).stream().map(StockService::toDto).toList();
        return SearchResultDto.of(records, q.offset(), q.limit());
    }

    /**
     * 区间内全部行情（DTO 形式），可限定 codes 列表。
     *
     * @param start      起始日期
     * @param end        结束日期
     * @param adjustflag 复权方式
     * @param codes      限定代码列表（null = 全部）
     * @return 日线 DTO 列表
     */
    public List<StockDailyDto> recordsInRange(java.time.LocalDate start, java.time.LocalDate end,
                                              int adjustflag, List<String> codes) {
        return repository.recordsInRange(start, end, adjustflag, codes).stream()
                .map(StockService::toDto).toList();
    }

    /**
     * 获取最新交易日波动最大的股票。
     *
     * @param limit 返回条数
     * @return 波动榜 DTO 列表
     */
    public List<HotSymbolDto> latestMovers(int limit) {
        return repository.latestMovers(limit).stream()
                .map(e -> new HotSymbolDto(
                        e.getCode(),
                        e.getClosePrice() == null ? null : e.getClosePrice().doubleValue(),
                        e.getPctChange() == null ? null : e.getPctChange().doubleValue(),
                        e.getVolume()))
                .toList();
    }

    /**
     * 搜索建議：根據用戶輸入的部分代碼返回最新交易日的匹配結果。
     *
     * @param query 搜索关键词
     * @param limit 返回条数
     * @return 搜索建议 DTO 列表
     */
    public List<StockSuggestionDto> suggest(String query, int limit) {
        return repository.suggest(query, limit).stream()
                .map(e -> new StockSuggestionDto(
                        e.getCode(),
                        e.getClosePrice() == null ? null : e.getClosePrice().doubleValue(),
                        e.getPctChange() == null ? null : e.getPctChange().doubleValue()))
                .toList();
    }

    /**
     * 区间内全部行情（领域对象形式），供指标引擎和回测使用。
     *
     * @param start      起始日期
     * @param end        结束日期
     * @param adjustflag 复权方式
     * @param codes      限定代码列表（null = 全部）
     * @return 领域记录列表
     */
    public List<StockDaily> domainRecordsInRange(java.time.LocalDate start, java.time.LocalDate end,
                                                 int adjustflag, List<String> codes) {
        return repository.recordsInRange(start, end, adjustflag, codes).stream()
                .map(StockDailyMapper::toDomain).toList();
    }

    /**
     * 日线表格查询（领域对象形式）。
     *
     * @param dto 查询参数 DTO
     * @return 领域记录列表
     */
    public List<StockDaily> domainSearch(StockDailyQueryDto dto) {
        return repository.searchDaily(dto.toDomain()).stream().map(StockDailyMapper::toDomain).toList();
    }

    /**
     * K线初始批次（领域对象形式）。
     *
     * @param dto       查询参数 DTO
     * @param batchSize 批次大小
     * @return 领域记录列表
     */
    public List<StockDaily> domainCandlestick(StockDailyQueryDto dto, int batchSize) {
        return repository.candlestick(dto.toDomain(), batchSize).stream().map(StockDailyMapper::toDomain).toList();
    }

    /**
     * 更早历史批次（领域对象形式）。
     *
     * @param dto       查询参数 DTO
     * @param before    截止日期
     * @param batchSize 批次大小
     * @return 领域记录列表
     */
    public List<StockDaily> domainOlderCandlestick(StockDailyQueryDto dto, java.time.LocalDate before, int batchSize) {
        return repository.olderCandlestick(dto.toDomain(), before, batchSize).stream()
                .map(StockDailyMapper::toDomain).toList();
    }

    /**
     * 区间内去重交易日（升序）。
     *
     * @param start      起始日期
     * @param end        结束日期
     * @param adjustflag 复权方式
     * @return 交易日列表
     */
    public List<java.time.LocalDate> tradeDates(java.time.LocalDate start, java.time.LocalDate end, int adjustflag) {
        return repository.tradeDates(start, end, adjustflag);
    }

    private static StockDailyDto toDto(StockDailyEntity e) {
        return new StockDailyDto(
                e.getCode(), e.getTradeDate(),
                d(e.getOpenPrice()), d(e.getHighPrice()), d(e.getLowPrice()), d(e.getClosePrice()),
                d(e.getPreclosePrice()), e.getVolume(), d(e.getAmount()),
                e.getAdjustflag() == null ? 0 : e.getAdjustflag(),
                d(e.getTurn()), e.getTradeStatus(), d(e.getPctChange()), e.getIsSt());
    }

    private static Double d(java.math.BigDecimal v) {
        return v == null ? null : v.doubleValue();
    }
}
