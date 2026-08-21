package com.quantization.module.stock;

import com.quantization.config.CacheConfig;
import com.quantization.module.stock.dto.HotSymbolDto;
import com.quantization.module.stock.dto.IndustryDailyDto;
import com.quantization.module.stock.dto.IndustryProsperityDto;
import com.quantization.module.stock.dto.IndexDailyDto;
import com.quantization.module.stock.dto.IndexMetadataDto;
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
 */
@Service
@Transactional(readOnly = true)
public class StockService {

    private final StockDailyRepository repository;
    private final IndexDailyRepository indexDailyRepository;
    private final IndexMetadataRepository indexMetadataRepository;
    private final IndustryDailyRepository industryDailyRepository;

    public StockService(
            StockDailyRepository repository,
            IndexDailyRepository indexDailyRepository,
            IndexMetadataRepository indexMetadataRepository,
            IndustryDailyRepository industryDailyRepository) {
        this.repository = repository;
        this.indexDailyRepository = indexDailyRepository;
        this.indexMetadataRepository = indexMetadataRepository;
        this.industryDailyRepository = industryDailyRepository;
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
                        (java.time.LocalDate) row[0],
                        (String) row[1],
                        row[2] instanceof Number n2 ? n2.doubleValue() : null,
                        (String) row[3],
                        (String) row[4],
                        row[5] instanceof Number n5 ? n5.doubleValue() : null))
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

        // 計算所有行業（一級+二級）的累計漲幅，排序
        List<RotationSignalDto.RankEntryDto> industryRanks = all.stream()
                .filter(e -> "industry_l1".equals(e.getCategoryCode()) || "industry_l2".equals(e.getCategoryCode()))
                .map(e -> {
                    List<IndexDailyDto> list = history.getOrDefault(e.getCode(), List.of());
                    Double change = cumulativeChange(list);
                    return new RotationSignalDto.RankEntryDto(e.getName() + "(" + e.getCode() + ")", change != null ? change : 0.0);
                })
                .sorted(Comparator.comparingDouble(RotationSignalDto.RankEntryDto::change).reversed())
                .toList();

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

    // ------------------------------------------------------------------------
    // 行業日聚合（新增）
    // ------------------------------------------------------------------------

    /**
     * 查詢指定日期的行業聚合數據，按平均漲跌幅倒序（走緩存）。
     *
     * @param tradeDate 交易日期，為空時取資料庫最新交易日
     * @return 行業聚合 DTO 列表
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "#p0 != null ? #p0.toString() : 'latest'")
    public List<IndustryDailyDto> industryDailyByDate(LocalDate tradeDate) {
        LocalDate target = tradeDate != null ? tradeDate : latestIndustryDailyDate();
        return industryDailyRepository.findByTradeDateOrderByAvgPctChgDesc(target).stream()
                .map(IndustryDailyDto::from)
                .toList();
    }

    private LocalDate latestIndustryDailyDate() {
        IndustryDailyEntity latest = industryDailyRepository.findFirstByOrderByTradeDateDesc();
        return latest != null ? latest.getTradeDate() : LocalDate.now();
    }

    /**
     * 查詢指定行業在日期區間內的聚合數據，按日期升序（走緩存）。
     *
     * @param industry 行業名稱
     * @param start    起始日期
     * @param end      結束日期
     * @return 行業聚合 DTO 列表
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "#p0 + '-' + #p1 + '-' + #p2")
    public List<IndustryDailyDto> industryDailyRange(String industry, LocalDate start, LocalDate end) {
        return industryDailyRepository.findByIndustryAndTradeDateBetweenOrderByTradeDateAsc(
                        industry, start, end).stream()
                .map(IndustryDailyDto::from)
                .toList();
    }

    /**
     * 查詢日期區間內全部行業的聚合數據（用於行業相關性矩陣計算）。
     *
     * @param start 起始日期
     * @param end   結束日期
     * @return 全部行業聚合 DTO 列表（按日期升序、行業升序）
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'all-' + #p0 + '-' + #p1")
    public List<IndustryDailyDto> allIndustryDailyRange(LocalDate start, LocalDate end) {
        return industryDailyRepository.findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(
                        start, end).stream()
                .map(IndustryDailyDto::from)
                .toList();
    }

    /**
     * 計算指定日期的行業景氣度指標（基於漲跌幅、成交額、換手率、漲跌家數綜合評分）。
     *
     * 評分維度（每維 0-100，加權綜合為 prosperityIndex）：
     * - momentumScore (權重 0.35): avgPctChg 標準化
     * - capitalScore (權重 0.25): totalAmount 標準化
     * - activityScore (權重 0.20): avgTurn 標準化
     * - breadthScore (權重 0.20): risingCount / (risingCount + fallingCount) 標準化
     *
     * @param tradeDate 交易日期，為空時取最新交易日
     * @return 行業景氣度 DTO 列表（按 prosperityIndex 倒序）
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'prosperity-' + (#p0 != null ? #p0.toString() : 'latest')")
    public List<IndustryProsperityDto> industryProsperity(LocalDate tradeDate) {
        LocalDate target = tradeDate != null ? tradeDate : latestIndustryDailyDate();
        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateOrderByAvgPctChgDesc(target);

        if (entities.isEmpty()) {
            return List.of();
        }

        // 提取各維度數據用於標準化
        double[] pctChgs = entities.stream()
                .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0)
                .toArray();
        double[] amounts = entities.stream()
                .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                .toArray();
        double[] turns = entities.stream()
                .mapToDouble(e -> e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0)
                .toArray();
        double[] breadths = entities.stream()
                .mapToDouble(e -> {
                    int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
                    int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
                    int total = rising + falling;
                    return total > 0 ? (double) rising / total * 100.0 : 50.0;
                })
                .toArray();

        // 計算各維度的 min/max 用於標準化
        double pctMin = min(pctChgs), pctMax = max(pctChgs);
        double amtMin = min(amounts), amtMax = max(amounts);
        double turnMin = min(turns), turnMax = max(turns);
        double breadthMin = min(breadths), breadthMax = max(breadths);

        return entities.stream().map(e -> {
            double pctChg = e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0;
            double amount = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
            double turn = e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0;
            int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
            int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
            int total = rising + falling;
            double breadth = total > 0 ? (double) rising / total * 100.0 : 50.0;

            // 標準化到 0-100
            double momentumScore = normalize(pctChg, pctMin, pctMax);
            double capitalScore = normalize(amount, amtMin, amtMax);
            double activityScore = normalize(turn, turnMin, turnMax);
            double breadthScore = normalize(breadth, breadthMin, breadthMax);

            // 加權綜合
            double prosperityIndex = momentumScore * 0.35
                    + capitalScore * 0.25
                    + activityScore * 0.20
                    + breadthScore * 0.20;

            String grade = prosperityIndex >= 80 ? "繁榮"
                    : prosperityIndex >= 65 ? "景氣"
                    : prosperityIndex >= 50 ? "平穩"
                    : prosperityIndex >= 35 ? "低迷"
                    : "衰退";

            return new IndustryProsperityDto(
                    e.getTradeDate(),
                    e.getIndustry(),
                    pctChg,
                    amount,
                    turn,
                    rising,
                    falling,
                    Math.round(momentumScore * 100.0) / 100.0,
                    Math.round(capitalScore * 100.0) / 100.0,
                    Math.round(activityScore * 100.0) / 100.0,
                    Math.round(breadthScore * 100.0) / 100.0,
                    Math.round(prosperityIndex * 100.0) / 100.0,
                    grade
            );
        }).sorted((a, b) -> Double.compare(b.prosperityIndex(), a.prosperityIndex())).toList();
    }

    /** 將值標準化到 0-100 區間。 */
    private static double normalize(double value, double min, double max) {
        if (max == min) {
            return 50.0; // 所有值相同時給中間分
        }
        return (value - min) / (max - min) * 100.0;
    }

    /**
     * 計算日期區間內每個交易日的行業景氣度（用於歷史趨勢圖）。
     *
     * @param start 起始日期
     * @param end   結束日期
     * @param topN  每個日期返回的行業數（按景氣度倒序），默認 15
     * @return 行業景氣度 DTO 列表（按日期升序、景氣度倒序）
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'prosperity-range-' + #p0 + '-' + #p1 + '-' + #p2")
    public List<IndustryProsperityDto> industryProsperityRange(LocalDate start, LocalDate end, int topN) {
        List<IndustryDailyEntity> allEntities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (allEntities.isEmpty()) {
            return List.of();
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : allEntities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<IndustryProsperityDto> result = new ArrayList<>();
        for (Map.Entry<LocalDate, List<IndustryDailyEntity>> entry : byDate.entrySet()) {
            List<IndustryDailyEntity> entities = entry.getValue();

            // 提取各維度數據用於標準化
            double[] pctChgs = entities.stream()
                    .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0)
                    .toArray();
            double[] amounts = entities.stream()
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .toArray();
            double[] turns = entities.stream()
                    .mapToDouble(e -> e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0)
                    .toArray();
            double[] breadths = entities.stream()
                    .mapToDouble(e -> {
                        int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
                        int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
                        int total = rising + falling;
                        return total > 0 ? (double) rising / total * 100.0 : 50.0;
                    })
                    .toArray();

            double pctMin = min(pctChgs), pctMax = max(pctChgs);
            double amtMin = min(amounts), amtMax = max(amounts);
            double turnMin = min(turns), turnMax = max(turns);
            double breadthMin = min(breadths), breadthMax = max(breadths);

            List<IndustryProsperityDto> dayResults = entities.stream().map(e -> {
                double pctChg = e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0;
                double amount = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
                double turn = e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0;
                int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
                int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
                int total = rising + falling;
                double breadth = total > 0 ? (double) rising / total * 100.0 : 50.0;

                double momentumScore = normalize(pctChg, pctMin, pctMax);
                double capitalScore = normalize(amount, amtMin, amtMax);
                double activityScore = normalize(turn, turnMin, turnMax);
                double breadthScore = normalize(breadth, breadthMin, breadthMax);

                double prosperityIndex = momentumScore * 0.35
                        + capitalScore * 0.25
                        + activityScore * 0.20
                        + breadthScore * 0.20;

                String grade = prosperityIndex >= 80 ? "繁榮"
                        : prosperityIndex >= 65 ? "景氣"
                        : prosperityIndex >= 50 ? "平穩"
                        : prosperityIndex >= 35 ? "低迷"
                        : "衰退";

                return new IndustryProsperityDto(
                        e.getTradeDate(),
                        e.getIndustry(),
                        pctChg,
                        amount,
                        turn,
                        rising,
                        falling,
                        Math.round(momentumScore * 100.0) / 100.0,
                        Math.round(capitalScore * 100.0) / 100.0,
                        Math.round(activityScore * 100.0) / 100.0,
                        Math.round(breadthScore * 100.0) / 100.0,
                        Math.round(prosperityIndex * 100.0) / 100.0,
                        grade
                );
            }).sorted((a, b) -> Double.compare(b.prosperityIndex(), a.prosperityIndex()))
                    .limit(topN)
                    .toList();

            result.addAll(dayResults);
        }

        return result;
    }

    private static double min(double[] arr) {
        double m = Double.MAX_VALUE;
        for (double v : arr) {
            if (v < m) m = v;
        }
        return m;
    }

    private static double max(double[] arr) {
        double m = -Double.MAX_VALUE;
        for (double v : arr) {
            if (v > m) m = v;
        }
        return m;
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
