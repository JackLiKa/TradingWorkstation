package com.quantization.module.stock;

import com.quantization.config.CacheConfig;
import com.quantization.module.stock.dto.HotSymbolDto;
import com.quantization.module.stock.dto.IndexDailyDto;
import com.quantization.module.stock.dto.MarketBreadthDto;
import com.quantization.module.stock.dto.RotationSignalDto;
import com.quantization.module.stock.dto.SectorPerformanceDto;
import com.quantization.module.stock.dto.SearchResultDto;
import com.quantization.module.stock.dto.StockDailyDto;
import com.quantization.module.stock.dto.StockDailyQueryDto;
import com.quantization.module.stock.dto.StockSuggestionDto;
import com.quantization.module.stock.dto.SummaryMetricsDto;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * 行情服务，封装股票日线的查询、汇总、K线加载和搜索建议等业务逻辑。
 * 提供 DTO 和领域对象两种返回形式，供 Controller 和其他模块复用。
 *
 * 行業聚合查詢、景氣度計算與預警已遷至 {@link com.quantization.module.industry.IndustryService}；
 * 輪動預測、季節性分析、Markov 模型、多模型預測已遷至
 * {@link com.quantization.module.forecast.ForecastService}。
 */
@Service
@Transactional(readOnly = true)
public class StockService {

    private final StockDailyRepository repository;
    private final IndexDailyRepository indexDailyRepository;
    private final IndexMetadataRepository indexMetadataRepository;
    private final IndustryDailyRepository industryDailyRepository;
    private final StockIndustryRepository stockIndustryRepository;

    public StockService(
            StockDailyRepository repository,
            IndexDailyRepository indexDailyRepository,
            IndexMetadataRepository indexMetadataRepository,
            IndustryDailyRepository industryDailyRepository,
            StockIndustryRepository stockIndustryRepository) {
        this.repository = repository;
        this.indexDailyRepository = indexDailyRepository;
        this.indexMetadataRepository = indexMetadataRepository;
        this.industryDailyRepository = industryDailyRepository;
        this.stockIndustryRepository = stockIndustryRepository;
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
     * 門面函数：批量查詢股票最新行業歸屬（供 backtest/screener 跨模塊調用，避免直插 Repository）。
     *
     * @param codes 股票代碼列表
     * @return Object[] 每行 [code, industryName]
     */
    public List<Object[]> findLatestIndustriesByCode(List<String> codes) {
        if (codes == null || codes.isEmpty()) return List.of();
        return stockIndustryRepository.findLatestIndustriesByCode(codes);
    }

    /**
     * 門面函数：查詢指數日線區間數據（供 backtest 跨模塊調用，避免直插 Repository）。
     *
     * @param code      指數代碼
     * @param startDate 起始日期
     * @param endDate   結束日期
     * @return 指數日線實體列表（按日期升序）
     */
    public List<IndexDailyEntity> findIndexDailyBetween(String code, java.time.LocalDate startDate, java.time.LocalDate endDate) {
        return indexDailyRepository.findByCodeAndTradeDateBetweenOrderByTradeDateAsc(code, startDate, endDate);
    }

    /**
     * 获取汇总指标（走缓存）。
     *
     * @return 汇总指标 DTO
     */
    @Cacheable(value = CacheConfig.SUMMARY_CACHE, key = "'summary'")
    public SummaryMetricsDto summaryMetrics() {
        StockSummaryProjection p = repository.summaryMetrics();
        return new SummaryMetricsDto(p.totalRecords(), p.totalSymbols(), p.earliestTradeDate(), p.latestTradeDate(),
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
     * 多日板塊表現：最近 N 個交易日，每日各行業平均漲跌幅 + 領漲股（走緩存）。
     *
     * @param days 最近交易日天數
     * @return 板塊表現 DTO 列表
     */
    @Cacheable(value = CacheConfig.SECTOR_PERFORMANCE_CACHE, key = "#days")
    @Transactional(readOnly = true)
    public List<SectorPerformanceDto> sectorPerformance(int days) {
        return repository.sectorPerformance(days).stream()
                .map(row -> new SectorPerformanceDto(
                        toLocalDate(row[0]),
                        (String) row[1],
                        row[2] instanceof Number n2 ? n2.doubleValue() : null,
                        (String) row[3],
                        (String) row[4],
                        row[5] instanceof Number n5 ? n5.doubleValue() : null))
                .toList();
    }

    /**
     * 將原生查詢返回的日期對象轉為 LocalDate。
     * Hibernate 原生查詢可能返回 java.sql.Date 或 java.time.LocalDate，需兼容處理。
     */
    private static java.time.LocalDate toLocalDate(Object value) {
        if (value == null) return null;
        if (value instanceof java.time.LocalDate ld) return ld;
        if (value instanceof java.sql.Date sd) return sd.toLocalDate();
        if (value instanceof java.util.Date ud) return ud.toInstant()
                .atZone(java.time.ZoneId.systemDefault()).toLocalDate();
        throw new IllegalStateException("無法將 " + value.getClass() + " 轉為 LocalDate");
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

    // ------------------------------------------------------------------------
    // 多維指數分析（新增）
    // ------------------------------------------------------------------------

    /**
     * 批量指數歷史查詢：一次查詢多個指數最近 N 日的日線。
     * 用於 AI 多維市場分析（大盤 + 風格 + 行業）。
     *
     * @param codes 指數代碼列表
     * @param days  最近天數
     * @return 按指數代碼分組的歷史數據
     */
    public Map<String, List<IndexDailyDto>> batchIndexHistory(List<String> codes, int days) {
        if (codes == null || codes.isEmpty()) {
            return Map.of();
        }
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusDays(days + 10); // 多取幾天以防非交易日
        List<IndexDailyEntity> entities = indexDailyRepository
                .findByCodeInAndTradeDateBetweenOrderByTradeDateAsc(codes, start, end);

        Map<String, List<IndexDailyEntity>> byCode = entities.stream()
                .collect(Collectors.groupingBy(IndexDailyEntity::getCode, LinkedHashMap::new, Collectors.toList()));

        Map<String, List<IndexDailyDto>> result = new LinkedHashMap<>();
        for (String code : codes) {
            List<IndexDailyEntity> list = byCode.getOrDefault(code, List.of());
            // 只取最近 days 條
            List<IndexDailyEntity> trimmed = list.size() > days ? list.subList(list.size() - days, list.size()) : list;
            result.put(code, trimmed.stream().map(IndexDailyDto::from).toList());
        }
        return result;
    }

    /**
     * 市場廣度分析：基於多類指數計算大盤/風格/行業的整體強弱（走緩存）。
     *
     * @param days 最近交易日天數
     * @return 市場廣度 DTO
     */
    @Cacheable(value = CacheConfig.MARKET_BREADTH_CACHE, key = "#days")
    public MarketBreadthDto marketBreadth(int days) {
        List<IndexMetadataEntity> all = indexMetadataRepository.findAllByOrderByCategoryCodeAscCodeAsc();
        List<String> codes = all.stream().map(IndexMetadataEntity::getCode).toList();
        Map<String, List<IndexDailyDto>> history = batchIndexHistory(codes, days);

        Map<String, Double> compositeBreadth = computeCategoryChange(all, history, "composite");
        Map<String, Double> scaleBreadth = computeCategoryChange(all, history, "scale");
        Map<String, Double> styleBreadth = computeCategoryChange(all, history, List.of("growth", "value"));

        // 計算所有分類的累計漲幅，找出領漲/滯漲
        Map<String, Double> allCategories = new LinkedHashMap<>();
        for (String catCode : all.stream().map(IndexMetadataEntity::getCategoryCode).distinct().toList()) {
            Map<String, Double> catMap = computeCategoryChange(all, history, catCode);
            double avg = catMap.values().stream().filter(Objects::nonNull).mapToDouble(Double::doubleValue).average().orElse(0.0);
            allCategories.put(catCode, avg);
        }

        List<Map.Entry<String, Double>> sorted = allCategories.entrySet().stream()
                .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                .toList();

        Map<String, Double> leadingCategories = new LinkedHashMap<>();
        Map<String, Double> laggingCategories = new LinkedHashMap<>();
        int topN = Math.max(1, sorted.size() / 3);
        for (int i = 0; i < sorted.size(); i++) {
            if (i < topN) {
                leadingCategories.put(sorted.get(i).getKey(), sorted.get(i).getValue());
            } else if (i >= sorted.size() - topN) {
                laggingCategories.put(sorted.get(i).getKey(), sorted.get(i).getValue());
            }
        }

        String summary = String.format(
                "最近 %d 日：綜合指數平均 %.2f%%，規模指數平均 %.2f%%，風格（成長-價值）差距 %.2f%%。",
                days,
                average(compositeBreadth.values()),
                average(scaleBreadth.values()),
                styleBreadth.getOrDefault("growth", 0.0) - styleBreadth.getOrDefault("value", 0.0)
        );

        return new MarketBreadthDto(days, compositeBreadth, scaleBreadth, styleBreadth,
                leadingCategories, laggingCategories, summary);
    }

    /**
     * 輪動信號分析：基於一級/二級行業指數和成長/價值指數計算輪動方向（走緩存）。
     *
     * @param days 最近交易日天數
     * @return 輪動信號 DTO
     */
    @Cacheable(value = CacheConfig.ROTATION_SIGNAL_CACHE, key = "#days")
    public RotationSignalDto rotationSignals(int days) {
        List<IndexMetadataEntity> all = indexMetadataRepository.findAllByOrderByCategoryCodeAscCodeAsc();
        List<String> codes = all.stream().map(IndexMetadataEntity::getCode).toList();
        Map<String, List<IndexDailyDto>> history = batchIndexHistory(codes, days);

        Map<String, Map<String, Double>> industryRotation = new LinkedHashMap<>();
        industryRotation.put("industry_l1", computeCategoryChange(all, history, "industry_l1"));
        industryRotation.put("industry_l2", computeCategoryChange(all, history, "industry_l2"));

        Map<String, Double> styleRotation = computeCategoryChange(all, history, List.of("growth", "value", "scale"));

        // 優先使用 industry_daily 表計算領漲/滯後行業（index_daily 可能缺行業指數數據）
        List<RotationSignalDto.RankEntryDto> industryRanks = computeIndustryRanksFromDaily(days);

        // 若 industry_daily 無數據，回退到 index_daily 計算
        if (industryRanks.isEmpty()) {
            industryRanks = all.stream()
                    .filter(e -> "industry_l1".equals(e.getCategoryCode()) || "industry_l2".equals(e.getCategoryCode()))
                    .map(e -> {
                        List<IndexDailyDto> list = history.getOrDefault(e.getCode(), List.of());
                        Double change = cumulativeChange(list);
                        return new RotationSignalDto.RankEntryDto(e.getName() + "(" + e.getCode() + ")", change != null ? change : 0.0);
                    })
                    .sorted(Comparator.comparingDouble(RotationSignalDto.RankEntryDto::change).reversed())
                    .toList();
        }

        int topN = Math.max(3, industryRanks.size() / 5);
        List<RotationSignalDto.RankEntryDto> leading = industryRanks.stream().limit(topN).toList();
        List<RotationSignalDto.RankEntryDto> lagging = industryRanks.stream().skip(Math.max(0, industryRanks.size() - topN)).toList();

        double rotationStrength = computeRotationStrength(industryRanks);

        String summary = String.format(
                "最近 %d 日：行業輪動強度 %.1f，領漲 %s，滯漲 %s。",
                days,
                rotationStrength,
                leading.isEmpty() ? "無" : leading.get(0).name(),
                lagging.isEmpty() ? "無" : lagging.get(0).name()
        );

        return new RotationSignalDto(days, industryRotation, styleRotation, leading, lagging, rotationStrength, summary);
    }

    /**
     * 從 industry_daily 表計算行業累計漲幅排名（用於輪動信號的領漲/滯後行業）。
     *
     * 取最近 N 個交易日的行業聚合數據，計算每個行業的累計平均漲跌幅。
     *
     * @param days 回溯天數
     * @return 行業排名列表（按累計漲幅倒序）
     */
    private List<RotationSignalDto.RankEntryDto> computeIndustryRanksFromDaily(int days) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusDays(days + 10);
        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return List.of();
        }

        // 按行業分組，計算累計漲跌幅（首日 avgPctChg → 末日 avgPctChg 的累計變化）
        Map<String, List<IndustryDailyEntity>> byIndustry = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byIndustry.computeIfAbsent(e.getIndustry(), k -> new ArrayList<>()).add(e);
        }

        List<RotationSignalDto.RankEntryDto> ranks = new ArrayList<>();
        for (Map.Entry<String, List<IndustryDailyEntity>> entry : byIndustry.entrySet()) {
            List<IndustryDailyEntity> list = entry.getValue();
            if (list.size() < 2) {
                continue;
            }
            // 累計漲跌幅 = 各日 avgPctChg 之和（近似累計收益）
            double cumulative = 0.0;
            for (IndustryDailyEntity e : list) {
                if (e.getAvgPctChg() != null) {
                    cumulative += e.getAvgPctChg().doubleValue();
                }
            }
            ranks.add(new RotationSignalDto.RankEntryDto(entry.getKey(), cumulative));
        }

        ranks.sort(Comparator.comparingDouble(RotationSignalDto.RankEntryDto::change).reversed());
        return ranks;
    }

    // ------------------------------------------------------------------------
    // 私有輔助方法
    // ------------------------------------------------------------------------

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

    private static double average(java.util.Collection<Double> values) {
        return values.stream().filter(Objects::nonNull).mapToDouble(Double::doubleValue).average().orElse(0.0);
    }

    private Map<String, Double> computeCategoryChange(
            List<IndexMetadataEntity> all,
            Map<String, List<IndexDailyDto>> history,
            String categoryCode) {
        return computeCategoryChange(all, history, List.of(categoryCode));
    }

    private Map<String, Double> computeCategoryChange(
            List<IndexMetadataEntity> all,
            Map<String, List<IndexDailyDto>> history,
            List<String> categoryCodes) {
        Map<String, Double> result = new LinkedHashMap<>();
        for (IndexMetadataEntity meta : all) {
            if (!categoryCodes.contains(meta.getCategoryCode())) {
                continue;
            }
            Double change = cumulativeChange(history.getOrDefault(meta.getCode(), List.of()));
            if (change != null) {
                result.put(meta.getName() + "(" + meta.getCode() + ")", change);
            }
        }
        return result;
    }

    private static Double cumulativeChange(List<IndexDailyDto> list) {
        if (list == null || list.size() < 2) {
            return null;
        }
        Double first = list.get(0).closePrice();
        Double last = list.get(list.size() - 1).closePrice();
        if (first == null || last == null || first == 0.0) {
            return null;
        }
        return (last - first) / first * 100.0;
    }

    private static double computeRotationStrength(List<RotationSignalDto.RankEntryDto> ranks) {
        if (ranks == null || ranks.isEmpty()) {
            return 0.0;
        }
        double[] values = ranks.stream().mapToDouble(RotationSignalDto.RankEntryDto::change).toArray();
        double mean = java.util.Arrays.stream(values).average().orElse(0.0);
        double variance = java.util.Arrays.stream(values)
                .map(v -> Math.pow(v - mean, 2))
                .average().orElse(0.0);
        double std = Math.sqrt(variance);
        // 標準差映射到 0-100：5% 對應 100
        return Math.min(100.0, std * 20.0);
    }
}
