package com.quantization.module.stock;

import com.quantization.config.CacheConfig;
import com.quantization.module.stock.dto.HotSymbolDto;
import com.quantization.module.stock.dto.IndustryDailyDto;
import com.quantization.module.stock.dto.IndustryProsperityDto;
import com.quantization.module.stock.dto.IndexDailyDto;
import com.quantization.module.stock.dto.IndexMetadataDto;
import com.quantization.module.stock.dto.MarketBreadthDto;
import com.quantization.module.stock.dto.RotationPredictionDto;
import com.quantization.module.stock.dto.RotationBacktestDto;
import com.quantization.module.stock.dto.RotationAutoMlDto;
import com.quantization.module.stock.dto.ProsperityAlertDto;
import com.quantization.module.stock.dto.ProsperitySeasonalityDto;
import com.quantization.module.stock.dto.ProsperityMarkovDto;
import com.quantization.module.stock.dto.ProsperityForecastDto;
import com.quantization.module.stock.dto.ProsperityForecastBacktestDto;
import com.quantization.module.stock.dto.RotationMarkovDto;
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
import java.util.HashMap;
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

    /**
     * 行業輪動預測 — 基於歷史輪動規律預測下一輪領漲行業。
     *
     * 預測模型綜合三個維度：
     * 1. 動量延續（權重 0.40）：近期累計漲跌幅，強者恆強
     * 2. 資金流向（權重 0.35）：成交金額佔比變化，資金流入更可能領漲
     * 3. 景氣度趨勢（權重 0.25）：景氣度變化趨勢，上升者更可能領漲
     *
     * @param lookbackDays 回溯天數（用於計算歷史輪動規律）
     * @return 輪動預測 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'rotation-prediction-' + #p0")
    public RotationPredictionDto predictRotation(int lookbackDays) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusDays(lookbackDays + 10);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new RotationPredictionDto(
                    end.toString(), lookbackDays + "日",
                    List.of(), List.of(), "數據不足，無法預測", 0.0
            );
        }

        // 按行業分組
        Map<String, List<IndustryDailyEntity>> byIndustry = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byIndustry.computeIfAbsent(e.getIndustry(), k -> new ArrayList<>()).add(e);
        }

        // 按日期分組（用於計算每日總成交額）
        Map<LocalDate, Double> dailyTotalAmount = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            double amt = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
            dailyTotalAmount.merge(e.getTradeDate(), amt, Double::sum);
        }

        List<LocalDate> sortedDates = new ArrayList<>(dailyTotalAmount.keySet());
        sortedDates.sort(LocalDate::compareTo);
        if (sortedDates.size() < 2) {
            return new RotationPredictionDto(
                    end.toString(), lookbackDays + "日",
                    List.of(), List.of(), "交易日不足，無法預測", 0.0
            );
        }

        LocalDate firstDate = sortedDates.get(0);
        LocalDate lastDate = sortedDates.get(sortedDates.size() - 1);
        double firstTotal = dailyTotalAmount.get(firstDate);
        double lastTotal = dailyTotalAmount.get(lastDate);

        // 計算每個行業的三個維度評分
        List<PredictionScore> scores = new ArrayList<>();
        for (Map.Entry<String, List<IndustryDailyEntity>> entry : byIndustry.entrySet()) {
            String industry = entry.getKey();
            List<IndustryDailyEntity> list = entry.getValue();
            if (list.size() < 2) continue;

            // 1. 動量：累計漲跌幅
            double momentum = 0.0;
            for (IndustryDailyEntity e : list) {
                if (e.getAvgPctChg() != null) {
                    momentum += e.getAvgPctChg().doubleValue();
                }
            }

            // 2. 資金流向：成交金額佔比變化
            double firstAmount = list.stream()
                    .filter(e -> e.getTradeDate().equals(firstDate))
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .findFirst().orElse(0.0);
            double lastAmount = list.stream()
                    .filter(e -> e.getTradeDate().equals(lastDate))
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .findFirst().orElse(0.0);
            double firstShare = firstTotal > 0 ? firstAmount / firstTotal : 0.0;
            double lastShare = lastTotal > 0 ? lastAmount / lastTotal : 0.0;
            double capitalFlow = (lastShare - firstShare) * 100.0; // 百分點變化

            // 3. 景氣度趨勢：近期漲跌幅趨勢（最後 5 日 vs 前 5 日）
            int midPoint = list.size() / 2;
            double firstHalfAvg = list.subList(0, Math.min(midPoint, list.size())).stream()
                    .filter(e -> e.getAvgPctChg() != null)
                    .mapToDouble(e -> e.getAvgPctChg().doubleValue())
                    .average().orElse(0.0);
            double lastHalfAvg = list.subList(midPoint, list.size()).stream()
                    .filter(e -> e.getAvgPctChg() != null)
                    .mapToDouble(e -> e.getAvgPctChg().doubleValue())
                    .average().orElse(0.0);
            double trendChange = lastHalfAvg - firstHalfAvg;

            scores.add(new PredictionScore(industry, momentum, capitalFlow, trendChange));
        }

        if (scores.isEmpty()) {
            return new RotationPredictionDto(
                    end.toString(), lookbackDays + "日",
                    List.of(), List.of(), "有效行業數不足，無法預測", 0.0
            );
        }

        // 標準化各維度到 0-100
        double momMin = scores.stream().mapToDouble(s -> s.momentum).min().orElse(0);
        double momMax = scores.stream().mapToDouble(s -> s.momentum).max().orElse(0);
        double capMin = scores.stream().mapToDouble(s -> s.capitalFlow).min().orElse(0);
        double capMax = scores.stream().mapToDouble(s -> s.capitalFlow).max().orElse(0);
        double trendMin = scores.stream().mapToDouble(s -> s.trendChange).min().orElse(0);
        double trendMax = scores.stream().mapToDouble(s -> s.trendChange).max().orElse(0);

        // 計算綜合評分
        List<RotationPredictionDto.PredictedIndustry> predictions = new ArrayList<>();
        for (PredictionScore s : scores) {
            double momScore = normalize(s.momentum, momMin, momMax);
            double capScore = normalize(s.capitalFlow, capMin, capMax);
            double trendScore = normalize(s.trendChange, trendMin, trendMax);

            double composite = momScore * 0.40 + capScore * 0.35 + trendScore * 0.25;

            String reason = String.format(
                    "動量%.1f(累計%.2f%%), 資金%.1f(佔比變化%.2f%%), 趨勢%.1f(後半段均漲%.3f%%)",
                    momScore, s.momentum, capScore, s.capitalFlow, trendScore, s.trendChange
            );

            predictions.add(new RotationPredictionDto.PredictedIndustry(
                    s.industry,
                    Math.round(composite * 100.0) / 100.0,
                    Math.round(momScore * 100.0) / 100.0,
                    Math.round(capScore * 100.0) / 100.0,
                    Math.round(trendScore * 100.0) / 100.0,
                    reason
            ));
        }

        // 按評分排序
        predictions.sort((a, b) -> Double.compare(b.score(), a.score()));

        // 取 Top 5 領漲和 Bottom 5 滯後
        List<RotationPredictionDto.PredictedIndustry> leaders = predictions.stream().limit(5).toList();
        List<RotationPredictionDto.PredictedIndustry> laggards = predictions.stream()
                .skip(Math.max(0, predictions.size() - 5))
                .toList();

        // 計算信心度（基於 Top 1 與中位數的差距）
        double topScore = leaders.isEmpty() ? 0 : leaders.get(0).score();
        double medianScore = predictions.size() > 0
                ? predictions.get(predictions.size() / 2).score()
                : 50.0;
        double confidence = Math.min(100.0, Math.max(0.0, (topScore - medianScore) * 2.0));

        // 構建預測理由
        String reasoning = String.format(
                "基於最近 %d 日數據，綜合動量(40%%)+資金流向(35%%)+景氣度趨勢(25%%)預測。" +
                "最可能領漲：%s（評分%.1f）。信心度%.1f%%。",
                lookbackDays,
                leaders.isEmpty() ? "無" : leaders.get(0).industry(),
                topScore,
                confidence
        );

        return new RotationPredictionDto(
                lastDate.toString(),
                lookbackDays + "日",
                leaders,
                laggards,
                reasoning,
                Math.round(confidence * 100.0) / 100.0
        );
    }

    /** 輪動預測內部評分數據。 */
    private record PredictionScore(String industry, double momentum, double capitalFlow, double trendChange) {
    }

    /**
     * 行業輪動預測回測 — 驗證歷史預測準確率。
     *
     * 回測邏輯：
     * 1. 取最近 backtestDays 的交易日列表
     * 2. 對每個交易日 T（排除最近 forwardDays 日，因為無法驗證）：
     *    - 用 T 之前 lookbackDays 的數據生成預測
     *    - 計算 T → T+forwardDays 內各行業實際累計漲跌幅
     *    - 檢查預測 Top 5 領漲是否在實際 Top 5 內（命中）
     *    - 計算預測領漲行業的平均收益 vs 市場平均收益（超額收益）
     * 3. 匯總命中率、平均超額收益
     *
     * @param lookbackDays  預測回溯天數
     * @param forwardDays   前瞻驗證天數
     * @param backtestDays  回測總天數
     * @return 回測結果 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'rotation-backtest-' + #p0 + '-' + #p1 + '-' + #p2")
    public RotationBacktestDto backtestRotationPrediction(int lookbackDays, int forwardDays, int backtestDays) {
        LocalDate today = LocalDate.now();
        LocalDate dataStart = today.minusDays(lookbackDays + backtestDays + forwardDays + 20);
        LocalDate dataEnd = today;

        List<IndustryDailyEntity> allEntities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(dataStart, dataEnd);

        if (allEntities.isEmpty()) {
            return new RotationBacktestDto(lookbackDays, forwardDays, 0, 0, 0, 0, 0, 0,
                    "數據不足，無法回測", List.of());
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : allEntities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < lookbackDays + forwardDays + 5) {
            return new RotationBacktestDto(lookbackDays, forwardDays, 0, 0, 0, 0, 0, 0,
                    "交易日不足，無法回測（需要至少 " + (lookbackDays + forwardDays + 5) + " 個交易日）", List.of());
        }

        // 回測窗口：從第 lookbackDays 個交易日開始，到倒數 forwardDays 個交易日結束
        int startIdx = Math.max(lookbackDays, 5);
        int endIdx = sortedDates.size() - forwardDays;

        List<RotationBacktestDto.BacktestEntry> entries = new ArrayList<>();
        int hitCount = 0;
        double totalLeaderReturn = 0.0;
        double totalLaggardReturn = 0.0;
        double totalMarketReturn = 0.0;

        // 每隔幾個交易日取樣一次（避免過多回測點）
        int step = Math.max(1, (endIdx - startIdx) / 30); // 最多 30 個回測點

        for (int i = startIdx; i < endIdx; i += step) {
            LocalDate predictDate = sortedDates.get(i);
            LocalDate actualEndDate = sortedDates.get(Math.min(i + forwardDays, sortedDates.size() - 1));

            // 1. 用 predictDate 之前 lookbackDays 的數據生成預測
            int windowStart = Math.max(0, i - lookbackDays);
            List<IndustryDailyEntity> windowData = new ArrayList<>();
            for (int j = windowStart; j <= i; j++) {
                windowData.addAll(byDate.get(sortedDates.get(j)));
            }

            List<String> predictedTop5 = predictTopIndustries(windowData, 5);
            if (predictedTop5.isEmpty()) continue;

            // 2. 計算 predictDate → actualEndDate 內各行業實際累計漲跌幅
            Map<String, Double> actualReturns = new HashMap<>();
            for (int j = i + 1; j <= Math.min(i + forwardDays, sortedDates.size() - 1); j++) {
                for (IndustryDailyEntity e : byDate.get(sortedDates.get(j))) {
                    if (e.getAvgPctChg() != null) {
                        actualReturns.merge(e.getIndustry(), e.getAvgPctChg().doubleValue(), Double::sum);
                    }
                }
            }

            if (actualReturns.isEmpty()) continue;

            // 3. 找出實際 Top 5 行業
            List<String> actualTop5 = actualReturns.entrySet().stream()
                    .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                    .limit(5)
                    .map(Map.Entry::getKey)
                    .toList();

            String actualTop = actualTop5.isEmpty() ? "無" : actualTop5.get(0);

            // 4. 計算預測領漲行業的實際收益
            String topPredicted = predictedTop5.get(0);
            double predictedReturn = actualReturns.getOrDefault(topPredicted, 0.0);
            double marketAvg = actualReturns.values().stream()
                    .mapToDouble(Double::doubleValue).average().orElse(0.0);
            double excessReturn = predictedReturn - marketAvg;

            // 5. 命中判定：預測 Top 5 與實際 Top 5 有交集
            boolean hit = predictedTop5.stream().anyMatch(actualTop5::contains);
            if (hit) hitCount++;

            totalLeaderReturn += predictedReturn;
            totalMarketReturn += marketAvg;
            entries.add(new RotationBacktestDto.BacktestEntry(
                    predictDate.toString(),
                    topPredicted,
                    actualTop,
                    Math.round(predictedReturn * 1000.0) / 1000.0,
                    Math.round(marketAvg * 1000.0) / 1000.0,
                    Math.round(excessReturn * 1000.0) / 1000.0,
                    hit
            ));
        }

        int total = entries.size();
        double hitRate = total > 0 ? (double) hitCount / total * 100.0 : 0.0;
        double avgLeaderReturn = total > 0 ? totalLeaderReturn / total : 0.0;
        double avgMarketReturn = total > 0 ? totalMarketReturn / total : 0.0;
        double avgExcessReturn = avgLeaderReturn - avgMarketReturn;

        String summary = String.format(
                "回測 %d 次（lookback=%d日, forward=%d日）。命中率 %.1f%%。" +
                "預測領漲平均收益 %.3f%%，市場平均 %.3f%%，超額收益 %.3f%%。",
                total, lookbackDays, forwardDays, hitRate,
                avgLeaderReturn, avgMarketReturn, avgExcessReturn
        );

        return new RotationBacktestDto(
                lookbackDays, forwardDays, total, hitCount,
                Math.round(hitRate * 100.0) / 100.0,
                Math.round(avgLeaderReturn * 1000.0) / 1000.0,
                Math.round(avgMarketReturn * 1000.0) / 1000.0,
                Math.round(avgExcessReturn * 1000.0) / 1000.0,
                summary,
                entries
        );
    }

    /**
     * 內部方法：用給定數據窗口預測 Top N 領漲行業。
     * 邏輯與 predictRotation 相同，但不依賴當前日期。
     */
    private List<String> predictTopIndustries(List<IndustryDailyEntity> windowData, int topN) {
        if (windowData == null || windowData.size() < 10) return List.of();

        // 按行業分組
        Map<String, List<IndustryDailyEntity>> byIndustry = new LinkedHashMap<>();
        for (IndustryDailyEntity e : windowData) {
            byIndustry.computeIfAbsent(e.getIndustry(), k -> new ArrayList<>()).add(e);
        }

        // 按日期分組計算每日總成交額
        Map<LocalDate, Double> dailyTotal = new LinkedHashMap<>();
        for (IndustryDailyEntity e : windowData) {
            double amt = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
            dailyTotal.merge(e.getTradeDate(), amt, Double::sum);
        }

        List<LocalDate> dates = new ArrayList<>(dailyTotal.keySet());
        dates.sort(LocalDate::compareTo);
        if (dates.size() < 2) return List.of();

        LocalDate firstDate = dates.get(0);
        LocalDate lastDate = dates.get(dates.size() - 1);
        double firstTotal = dailyTotal.get(firstDate);
        double lastTotal = dailyTotal.get(lastDate);

        List<PredictionScore> scores = new ArrayList<>();
        for (Map.Entry<String, List<IndustryDailyEntity>> entry : byIndustry.entrySet()) {
            List<IndustryDailyEntity> list = entry.getValue();
            if (list.size() < 2) continue;

            double momentum = 0.0;
            for (IndustryDailyEntity e : list) {
                if (e.getAvgPctChg() != null) momentum += e.getAvgPctChg().doubleValue();
            }

            double firstAmount = list.stream()
                    .filter(e -> e.getTradeDate().equals(firstDate))
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .findFirst().orElse(0.0);
            double lastAmount = list.stream()
                    .filter(e -> e.getTradeDate().equals(lastDate))
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .findFirst().orElse(0.0);
            double firstShare = firstTotal > 0 ? firstAmount / firstTotal : 0.0;
            double lastShare = lastTotal > 0 ? lastAmount / lastTotal : 0.0;
            double capitalFlow = (lastShare - firstShare) * 100.0;

            int midPoint = list.size() / 2;
            double firstHalfAvg = list.subList(0, Math.min(midPoint, list.size())).stream()
                    .filter(e -> e.getAvgPctChg() != null)
                    .mapToDouble(e -> e.getAvgPctChg().doubleValue())
                    .average().orElse(0.0);
            double lastHalfAvg = list.subList(midPoint, list.size()).stream()
                    .filter(e -> e.getAvgPctChg() != null)
                    .mapToDouble(e -> e.getAvgPctChg().doubleValue())
                    .average().orElse(0.0);
            double trendChange = lastHalfAvg - firstHalfAvg;

            scores.add(new PredictionScore(entry.getKey(), momentum, capitalFlow, trendChange));
        }

        if (scores.isEmpty()) return List.of();

        // 標準化
        double momMin = scores.stream().mapToDouble(s -> s.momentum).min().orElse(0);
        double momMax = scores.stream().mapToDouble(s -> s.momentum).max().orElse(0);
        double capMin = scores.stream().mapToDouble(s -> s.capitalFlow).min().orElse(0);
        double capMax = scores.stream().mapToDouble(s -> s.capitalFlow).max().orElse(0);
        double trendMin = scores.stream().mapToDouble(s -> s.trendChange).min().orElse(0);
        double trendMax = scores.stream().mapToDouble(s -> s.trendChange).max().orElse(0);

        // 計算綜合評分並排序
        List<Map.Entry<String, Double>> ranked = new ArrayList<>();
        for (PredictionScore s : scores) {
            double momScore = normalize(s.momentum, momMin, momMax);
            double capScore = normalize(s.capitalFlow, capMin, capMax);
            double trendScore = normalize(s.trendChange, trendMin, trendMax);
            double composite = momScore * 0.40 + capScore * 0.35 + trendScore * 0.25;
            ranked.add(Map.entry(s.industry, composite));
        }

        ranked.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));
        return ranked.stream().limit(topN).map(Map.Entry::getKey).toList();
    }

    /**
     * 輪動預測 AutoML 自動調參 — 自動尋找最佳 lookbackDays × forwardDays 組合。
     *
     * 搜尋空間：
     * - lookbackDays: [5, 10, 15, 20, 30]
     * - forwardDays: [3, 5, 10]
     * 共 15 組合，每組用 backtestDays 回測。
     *
     * 評分公式：compositeScore = hitRate * 0.6 + excessReturnNormalized * 0.4
     *
     * @param backtestDays 回測總天數（默認 90）
     * @return AutoML 結果 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'rotation-automl-' + #p0")
    public RotationAutoMlDto autoTuneRotationPrediction(int backtestDays) {
        int[] lookbackOptions = {5, 10, 15, 20, 30};
        int[] forwardOptions = {3, 5, 10};

        List<RotationAutoMlDto.ParamCombination> combinations = new ArrayList<>();

        for (int lookback : lookbackOptions) {
            for (int forward : forwardOptions) {
                RotationBacktestDto bt = backtestRotationPrediction(lookback, forward, backtestDays);
                if (bt.totalPredictions() == 0) {
                    combinations.add(new RotationAutoMlDto.ParamCombination(
                            lookback, forward, 0, 0, 0, 0, 0));
                    continue;
                }
                combinations.add(new RotationAutoMlDto.ParamCombination(
                        lookback, forward,
                        bt.hitRate(), bt.avgExcessReturn(), bt.avgLeaderReturn(),
                        bt.totalPredictions(), 0 // compositeScore 稍後計算
                ));
            }
        }

        // 標準化超額收益到 0-100
        double minExcess = combinations.stream().mapToDouble(c -> c.avgExcessReturn()).min().orElse(0);
        double maxExcess = combinations.stream().mapToDouble(c -> c.avgExcessReturn()).max().orElse(0);

        // 計算綜合評分
        List<RotationAutoMlDto.ParamCombination> scored = new ArrayList<>();
        for (RotationAutoMlDto.ParamCombination c : combinations) {
            double excessNorm = normalize(c.avgExcessReturn(), minExcess, maxExcess);
            double composite = c.hitRate() * 0.6 + excessNorm * 0.4;
            scored.add(new RotationAutoMlDto.ParamCombination(
                    c.lookbackDays(), c.forwardDays(),
                    c.hitRate(), c.avgExcessReturn(), c.avgLeaderReturn(),
                    c.totalPredictions(),
                    Math.round(composite * 100.0) / 100.0
            ));
        }

        // 按綜合評分排序
        scored.sort((a, b) -> Double.compare(b.compositeScore(), a.compositeScore()));

        RotationAutoMlDto.ParamCombination best = scored.isEmpty() ? null : scored.get(0);

        String summary = best == null
                ? "數據不足，無法調參"
                : String.format(
                        "最佳參數：lookback=%d日, forward=%d日。命中率 %.1f%%，超額收益 %.3f%%，綜合評分 %.1f。",
                        best.lookbackDays(), best.forwardDays(),
                        best.hitRate(), best.avgExcessReturn(), best.compositeScore()
                );

        return new RotationAutoMlDto(
                best == null ? 0 : best.lookbackDays(),
                best == null ? 0 : best.forwardDays(),
                best == null ? 0 : best.hitRate(),
                best == null ? 0 : best.avgExcessReturn(),
                best == null ? 0 : best.compositeScore(),
                summary,
                scored
        );
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

    /**
     * 行業景氣度異常預警 — 檢測最新交易日 vs 前一交易日的景氣度突變與等級躍遷。
     *
     * 預警類型：
     * 1. surge（景氣度突升）：變化 ≥ threshold
     * 2. plunge（景氣度突降）：變化 ≤ -threshold
     * 3. grade_up（等級躍升）：等級從低到高
     * 4. grade_down（等級躍降）：等級從高到低
     *
     * @param threshold 突變閾值（默認 10.0）
     * @return 景氣度預警 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'prosperity-alert-' + #p0")
    public ProsperityAlertDto prosperityAlerts(double threshold) {
        LocalDate today = LocalDate.now();
        LocalDate start = today.minusDays(10);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, today);

        if (entities.isEmpty()) {
            return new ProsperityAlertDto(today.toString(), List.of(), "數據不足，無法檢測異常");
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < 2) {
            return new ProsperityAlertDto(today.toString(), List.of(), "交易日不足，無法對比");
        }

        LocalDate latestDate = sortedDates.get(sortedDates.size() - 1);
        LocalDate prevDate = sortedDates.get(sortedDates.size() - 2);

        List<IndustryDailyEntity> todayEntities = byDate.get(latestDate);
        List<IndustryDailyEntity> yesterdayEntities = byDate.get(prevDate);

        // 計算今日和昨日的景氣度
        Map<String, Double> todayProsperity = computeProsperityMap(todayEntities);
        Map<String, Double> yesterdayProsperity = computeProsperityMap(yesterdayEntities);

        List<ProsperityAlertDto.AlertEntry> alerts = new ArrayList<>();

        for (String industry : todayProsperity.keySet()) {
            Double todayVal = todayProsperity.get(industry);
            Double yesterdayVal = yesterdayProsperity.get(industry);
            if (todayVal == null || yesterdayVal == null) continue;

            double change = todayVal - yesterdayVal;
            String todayGrade = prosperityGrade(todayVal);
            String yesterdayGrade = prosperityGrade(yesterdayVal);

            String alertType = null;
            String alertTypeName = null;
            String severity = null;

            // 景氣度突升
            if (change >= threshold * 2) {
                alertType = "surge";
                alertTypeName = "景氣度突升";
                severity = "high";
            } else if (change >= threshold) {
                alertType = "surge";
                alertTypeName = "景氣度上升";
                severity = "medium";
            }

            // 景氣度突降
            if (change <= -threshold * 2) {
                alertType = "plunge";
                alertTypeName = "景氣度突降";
                severity = "high";
            } else if (change <= -threshold && alertType == null) {
                alertType = "plunge";
                alertTypeName = "景氣度下降";
                severity = "medium";
            }

            // 等級躍遷
            int todayGradeLevel = gradeLevel(todayGrade);
            int yesterdayGradeLevel = gradeLevel(yesterdayGrade);
            if (todayGradeLevel > yesterdayGradeLevel) {
                // 等級躍升（如 低迷 → 景氣）
                if (todayGradeLevel - yesterdayGradeLevel >= 2) {
                    alerts.add(new ProsperityAlertDto.AlertEntry(
                            industry, "grade_up", "等級躍升",
                            Math.round(yesterdayVal * 100.0) / 100.0,
                            Math.round(todayVal * 100.0) / 100.0,
                            Math.round(change * 100.0) / 100.0,
                            yesterdayGrade, todayGrade, "high",
                            String.format("%s 等級從「%s」躍升到「%s」（景氣度 %.1f → %.1f）",
                                    industry, yesterdayGrade, todayGrade, yesterdayVal, todayVal)
                    ));
                } else if (alertType == null) {
                    alerts.add(new ProsperityAlertDto.AlertEntry(
                            industry, "grade_up", "等級上升",
                            Math.round(yesterdayVal * 100.0) / 100.0,
                            Math.round(todayVal * 100.0) / 100.0,
                            Math.round(change * 100.0) / 100.0,
                            yesterdayGrade, todayGrade, "medium",
                            String.format("%s 等級從「%s」上升到「%s」",
                                    industry, yesterdayGrade, todayGrade)
                    ));
                }
            } else if (todayGradeLevel < yesterdayGradeLevel) {
                // 等級躍降
                if (yesterdayGradeLevel - todayGradeLevel >= 2) {
                    alerts.add(new ProsperityAlertDto.AlertEntry(
                            industry, "grade_down", "等級躍降",
                            Math.round(yesterdayVal * 100.0) / 100.0,
                            Math.round(todayVal * 100.0) / 100.0,
                            Math.round(change * 100.0) / 100.0,
                            yesterdayGrade, todayGrade, "high",
                            String.format("%s 等級從「%s」躍降到「%s」（景氣度 %.1f → %.1f）",
                                    industry, yesterdayGrade, todayGrade, yesterdayVal, todayVal)
                    ));
                } else if (alertType == null) {
                    alerts.add(new ProsperityAlertDto.AlertEntry(
                            industry, "grade_down", "等級下降",
                            Math.round(yesterdayVal * 100.0) / 100.0,
                            Math.round(todayVal * 100.0) / 100.0,
                            Math.round(change * 100.0) / 100.0,
                            yesterdayGrade, todayGrade, "medium",
                            String.format("%s 等級從「%s」下降到「%s」",
                                    industry, yesterdayGrade, todayGrade)
                    ));
                }
            }

            // 景氣度突變（未伴隨等級變化時單獨記錄）
            if (alertType != null && todayGradeLevel == yesterdayGradeLevel) {
                String message = alertType.equals("surge")
                        ? String.format("%s 景氣度突升 %.1f → %.1f（+%s）",
                                industry, yesterdayVal, todayVal, String.format("%.1f", change))
                        : String.format("%s 景氣度突降 %.1f → %.1f（%s）",
                                industry, yesterdayVal, todayVal, String.format("%.1f", change));
                alerts.add(new ProsperityAlertDto.AlertEntry(
                        industry, alertType, alertTypeName,
                        Math.round(yesterdayVal * 100.0) / 100.0,
                        Math.round(todayVal * 100.0) / 100.0,
                        Math.round(change * 100.0) / 100.0,
                        yesterdayGrade, todayGrade, severity, message
                ));
            }
        }

        // 按嚴重程度和變化幅度排序
        alerts.sort((a, b) -> {
            int sa = severityRank(a.severity());
            int sb = severityRank(b.severity());
            if (sa != sb) return sb - sa;
            return Double.compare(Math.abs(b.change()), Math.abs(a.change()));
        });

        String summary = String.format(
                "分析日期 %s（對比 %s → %s）：共檢測到 %d 條預警（%d 條高嚴重度）。",
                latestDate, prevDate, latestDate, alerts.size(),
                alerts.stream().filter(a -> "high".equals(a.severity())).count()
        );

        return new ProsperityAlertDto(latestDate.toString(), alerts, summary);
    }

    /**
     * 行業景氣度週期性分析 — 檢測季節性模式與週期規律。
     *
     * 分析維度：
     * 1. 月度模式：各行業在每個月的平均景氣度（1-12月）
     * 2. 星期模式：各行業在每個星期的平均景氣度（週一至週五）
     * 3. 季節性強度：月度方差 / 總方差（0-1，越高季節性越明顯）
     * 4. 最佳/最差月份
     *
     * @param months 分析回溯月數（默認 12）
     * @return 週期性分析 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'prosperity-seasonality-' + #p0")
    public ProsperitySeasonalityDto prosperitySeasonality(int months) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusMonths(months);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new ProsperitySeasonalityDto(
                    start + " ~ " + end, 0, Map.of(), "數據不足，無法分析週期性");
        }

        // 按行業分組
        Map<String, List<IndustryDailyEntity>> byIndustry = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byIndustry.computeIfAbsent(e.getIndustry(), k -> new ArrayList<>()).add(e);
        }

        // 按日期分組（用於計算每日景氣度）
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        // 預計算每個交易日的景氣度 Map
        Map<LocalDate, Map<String, Double>> dailyProsperity = new LinkedHashMap<>();
        for (Map.Entry<LocalDate, List<IndustryDailyEntity>> entry : byDate.entrySet()) {
            dailyProsperity.put(entry.getKey(), computeProsperityMap(entry.getValue()));
        }

        Map<String, ProsperitySeasonalityDto.MonthlyPattern> industryPatterns = new LinkedHashMap<>();

        for (String industry : byIndustry.keySet()) {
            // 收集該行業所有交易日的景氣度
            List<double[]> monthValues = new ArrayList<>(); // [month, prosperity]
            List<double[]> weekdayValues = new ArrayList<>(); // [weekday, prosperity]
            List<Double> allValues = new ArrayList<>();

            for (Map.Entry<LocalDate, Map<String, Double>> dp : dailyProsperity.entrySet()) {
                Double val = dp.getValue().get(industry);
                if (val == null) continue;

                int month = dp.getKey().getMonthValue();
                int weekday = dp.getKey().getDayOfWeek().getValue(); // 1=Monday, 7=Sunday

                monthValues.add(new double[]{month, val});
                weekdayValues.add(new double[]{weekday, val});
                allValues.add(val);
            }

            if (allValues.isEmpty()) continue;

            // 計算月度平均
            Map<Integer, Double> monthlyAvg = new LinkedHashMap<>();
            Map<Integer, List<Double>> monthlyBuckets = new LinkedHashMap<>();
            for (double[] mv : monthValues) {
                int m = (int) mv[0];
                monthlyBuckets.computeIfAbsent(m, k -> new ArrayList<>()).add(mv[1]);
            }
            for (Map.Entry<Integer, List<Double>> me : monthlyBuckets.entrySet()) {
                double avg = me.getValue().stream().mapToDouble(Double::doubleValue).average().orElse(0);
                monthlyAvg.put(me.getKey(), Math.round(avg * 100.0) / 100.0);
            }

            // 計算星期平均
            Map<Integer, Double> weekdayAvg = new LinkedHashMap<>();
            Map<Integer, List<Double>> weekdayBuckets = new LinkedHashMap<>();
            for (double[] wv : weekdayValues) {
                int w = (int) wv[0];
                if (w <= 5) { // 只取週一至週五
                    weekdayBuckets.computeIfAbsent(w, k -> new ArrayList<>()).add(wv[1]);
                }
            }
            for (Map.Entry<Integer, List<Double>> we : weekdayBuckets.entrySet()) {
                double avg = we.getValue().stream().mapToDouble(Double::doubleValue).average().orElse(0);
                weekdayAvg.put(we.getKey(), Math.round(avg * 100.0) / 100.0);
            }

            // 找最佳/最差月份
            int bestMonth = 1, worstMonth = 1;
            double bestAvg = -1, worstAvg = 999;
            for (Map.Entry<Integer, Double> me : monthlyAvg.entrySet()) {
                if (me.getValue() > bestAvg) {
                    bestAvg = me.getValue();
                    bestMonth = me.getKey();
                }
                if (me.getValue() < worstAvg) {
                    worstAvg = me.getValue();
                    worstMonth = me.getKey();
                }
            }

            // 計算季節性強度（月度方差 / 總方差）
            double overallAvg = allValues.stream().mapToDouble(Double::doubleValue).average().orElse(0);
            double totalVariance = allValues.stream()
                    .mapToDouble(v -> Math.pow(v - overallAvg, 2)).sum() / allValues.size();
            double monthlyVariance = 0;
            for (Map.Entry<Integer, List<Double>> me : monthlyBuckets.entrySet()) {
                double mAvg = me.getValue().stream().mapToDouble(Double::doubleValue).average().orElse(0);
                monthlyVariance += me.getValue().size() * Math.pow(mAvg - overallAvg, 2);
            }
            monthlyVariance /= allValues.size();
            double seasonalityStrength = totalVariance > 0 ? monthlyVariance / totalVariance : 0;
            seasonalityStrength = Math.min(1.0, Math.max(0.0, seasonalityStrength));

            industryPatterns.put(industry, new ProsperitySeasonalityDto.MonthlyPattern(
                    industry,
                    monthlyAvg,
                    weekdayAvg,
                    bestMonth, worstMonth,
                    Math.round(bestAvg * 100.0) / 100.0,
                    Math.round(worstAvg * 100.0) / 100.0,
                    Math.round(seasonalityStrength * 1000.0) / 1000.0,
                    Math.round(overallAvg * 100.0) / 100.0
            ));
        }

        // 找出季節性最強的行業
        List<Map.Entry<String, ProsperitySeasonalityDto.MonthlyPattern>> sortedBySeasonality =
                new ArrayList<>(industryPatterns.entrySet());
        sortedBySeasonality.sort((a, b) -> Double.compare(
                b.getValue().seasonalityStrength(), a.getValue().seasonalityStrength()));

        String summary = String.format(
                "分析區間 %s ~ %s，共 %d 個數據點，%d 個行業。" +
                "季節性最強：%s（強度 %.2f，最佳月份 %d月，最差月份 %d月）。",
                start, end, entities.size(), industryPatterns.size(),
                sortedBySeasonality.isEmpty() ? "無" : sortedBySeasonality.get(0).getKey(),
                sortedBySeasonality.isEmpty() ? 0 : sortedBySeasonality.get(0).getValue().seasonalityStrength(),
                sortedBySeasonality.isEmpty() ? 0 : sortedBySeasonality.get(0).getValue().bestMonth(),
                sortedBySeasonality.isEmpty() ? 0 : sortedBySeasonality.get(0).getValue().worstMonth()
        );

        return new ProsperitySeasonalityDto(
                start + " ~ " + end,
                entities.size(),
                industryPatterns,
                summary
        );
    }

    /**
     * 行業景氣度 Markov 狀態轉移模型 — 預測等級轉換概率。
     *
     * 將景氣度分為 5 個狀態：1=衰退, 2=低迷, 3=平穩, 4=景氣, 5=繁榮
     * 基於歷史等級轉換構建一階 Markov 轉移矩陣。
     *
     * @param months 分析回溯月數（默認 12）
     * @return Markov 分析 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'prosperity-markov-' + #p0")
    public ProsperityMarkovDto prosperityMarkov(int months) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusMonths(months);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new ProsperityMarkovDto(end.toString(), 0, Map.of(), "數據不足，無法構建 Markov 模型");
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < 3) {
            return new ProsperityMarkovDto(end.toString(), 0, Map.of(), "交易日不足，無法構建 Markov 模型");
        }

        // 預計算每個交易日的景氣度 Map
        Map<LocalDate, Map<String, Double>> dailyProsperity = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            dailyProsperity.put(date, computeProsperityMap(byDate.get(date)));
        }

        // 按行業收集每日景氣度序列
        Map<String, List<LocalDate>> industryDates = new LinkedHashMap<>();
        Map<String, List<Double>> industrySeries = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            Map<String, Double> dp = dailyProsperity.get(date);
            for (Map.Entry<String, Double> e : dp.entrySet()) {
                industryDates.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(date);
                industrySeries.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(e.getValue());
            }
        }

        Map<String, ProsperityMarkovDto.IndustryMarkov> result = new LinkedHashMap<>();
        int totalTransitions = 0;

        for (String industry : industrySeries.keySet()) {
            List<Double> series = industrySeries.get(industry);
            if (series.size() < 3) continue;

            // 將景氣度轉為等級序列
            int[] gradeSeries = new int[series.size()];
            for (int i = 0; i < series.size(); i++) {
                gradeSeries[i] = gradeLevel(prosperityGrade(series.get(i)));
            }

            // 構建 5x5 轉移計數矩陣
            int[][] counts = new int[5][5];
            for (int i = 0; i < gradeSeries.length - 1; i++) {
                int from = gradeSeries[i] - 1; // 0-indexed
                int to = gradeSeries[i + 1] - 1;
                if (from >= 0 && from < 5 && to >= 0 && to < 5) {
                    counts[from][to]++;
                    totalTransitions++;
                }
            }

            // 轉為概率矩陣
            double[][] matrix = new double[5][5];
            for (int i = 0; i < 5; i++) {
                int rowSum = 0;
                for (int j = 0; j < 5; j++) rowSum += counts[i][j];
                for (int j = 0; j < 5; j++) {
                    matrix[i][j] = rowSum > 0 ? (double) counts[i][j] / rowSum : 0.0;
                    matrix[i][j] = Math.round(matrix[i][j] * 10000.0) / 10000.0;
                }
                // 若該行全零（無數據），設為均勻分布
                if (rowSum == 0) {
                    for (int j = 0; j < 5; j++) matrix[i][j] = 0.2;
                }
            }

            // 當前等級
            int currentState = gradeSeries[gradeSeries.length - 1];
            String currentStateName = gradeName(currentState);

            // 下一日各等級概率
            Map<Integer, Double> nextProb = new LinkedHashMap<>();
            int currentIdx = currentState - 1;
            for (int j = 0; j < 5; j++) {
                nextProb.put(j + 1, matrix[currentIdx][j]);
            }

            // 找最可能的下一等級
            int mostLikelyNext = 1;
            double mostLikelyProb = 0;
            for (int j = 0; j < 5; j++) {
                if (matrix[currentIdx][j] > mostLikelyProb) {
                    mostLikelyProb = matrix[currentIdx][j];
                    mostLikelyNext = j + 1;
                }
            }

            // 計算穩態分布（迭代法：P^n 收斂）
            Map<Integer, Double> steadyState = computeSteadyState(matrix);

            int transitionCount = 0;
            for (int i = 0; i < 5; i++) {
                for (int j = 0; j < 5; j++) transitionCount += counts[i][j];
            }

            result.put(industry, new ProsperityMarkovDto.IndustryMarkov(
                    industry,
                    matrix,
                    currentState,
                    currentStateName,
                    nextProb,
                    steadyState,
                    transitionCount,
                    gradeName(mostLikelyNext),
                    Math.round(mostLikelyProb * 1000.0) / 1000.0
            ));
        }

        String summary = String.format(
                "分析區間 %s ~ %s，共 %d 次等級轉換，%d 個行業。",
                start, end, totalTransitions, result.size()
        );

        return new ProsperityMarkovDto(end.toString(), totalTransitions, result, summary);
    }

    /** 計算 Markov 鏈的穩態分布（迭代法）。 */
    private Map<Integer, Double> computeSteadyState(double[][] matrix) {
        // 初始均勻分布
        double[] state = {0.2, 0.2, 0.2, 0.2, 0.2};
        // 迭代 1000 次或收斂
        for (int iter = 0; iter < 1000; iter++) {
            double[] newState = new double[5];
            for (int j = 0; j < 5; j++) {
                for (int i = 0; i < 5; i++) {
                    newState[j] += state[i] * matrix[i][j];
                }
            }
            // 檢查收斂
            double maxDiff = 0;
            for (int i = 0; i < 5; i++) {
                maxDiff = Math.max(maxDiff, Math.abs(newState[i] - state[i]));
            }
            System.arraycopy(newState, 0, state, 0, 5);
            if (maxDiff < 1e-8) break;
        }

        Map<Integer, Double> result = new LinkedHashMap<>();
        for (int i = 0; i < 5; i++) {
            result.put(i + 1, Math.round(state[i] * 10000.0) / 10000.0);
        }
        return result;
    }

    /** 等級數值轉名稱。 */
    private static String gradeName(int level) {
        return switch (level) {
            case 5 -> "繁榮";
            case 4 -> "景氣";
            case 3 -> "平穩";
            case 2 -> "低迷";
            case 1 -> "衰退";
            default -> "未知";
        };
    }

    /**
     * 行業景氣度多模型預測 — 整合 ARIMA、Holt-Winters、線性回歸。
     *
     * 三個模型均為純 Java 實作，CPU 秒級運算：
     * 1. ARIMA：簡化版 AR(2) + 一階差分
     * 2. Holt-Winters：三重指數平滑
     * 3. 線性回歸：OLS 趨勢預測
     *
     * @param months        分析回溯月數（默認 6）
     * @param forecastDays  預測天數（默認 5）
     * @return 多模型預測 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'prosperity-forecast-' + #p0 + '-' + #p1")
    public ProsperityForecastDto prosperityForecast(int months, int forecastDays) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusMonths(months);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new ProsperityForecastDto(end.toString(), forecastDays, Map.of(), "數據不足，無法預測");
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < 10) {
            return new ProsperityForecastDto(end.toString(), forecastDays, Map.of(), "交易日不足，無法預測（需至少 10 日）");
        }

        // 預計算每日景氣度
        Map<LocalDate, Map<String, Double>> dailyProsperity = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            dailyProsperity.put(date, computeProsperityMap(byDate.get(date)));
        }

        // 按行業收集序列
        Map<String, List<Double>> industrySeries = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            Map<String, Double> dp = dailyProsperity.get(date);
            for (Map.Entry<String, Double> e : dp.entrySet()) {
                industrySeries.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(e.getValue());
            }
        }

        // 生成預測日期（跳過週末）
        List<String> forecastDates = new ArrayList<>();
        LocalDate forecastDate = sortedDates.get(sortedDates.size() - 1);
        int added = 0;
        while (added < forecastDays) {
            forecastDate = forecastDate.plusDays(1);
            int dow = forecastDate.getDayOfWeek().getValue();
            if (dow <= 5) {
                forecastDates.add(forecastDate.toString());
                added++;
            }
        }

        Map<String, ProsperityForecastDto.IndustryForecast> result = new LinkedHashMap<>();

        for (Map.Entry<String, List<Double>> entry : industrySeries.entrySet()) {
            String industry = entry.getKey();
            List<Double> series = entry.getValue();
            if (series.size() < 10) continue;

            double[] data = series.stream().mapToDouble(Double::doubleValue).toArray();

            // 1. ARIMA 預測（簡化版 AR(2) + 一階差分）
            double[] arimaForecast = forecastARIMA(data, forecastDays);

            // 2. Holt-Winters 預測（三重指數平滑，季節週期=5）
            double[] hwForecast = forecastHoltWinters(data, forecastDays, 5);

            // 3. 線性回歸預測
            double[] linearForecast = forecastLinearRegression(data, forecastDays);

            // 4. 整合預測（加權平均：ARIMA 0.35, Holt-Winters 0.35, 線性回歸 0.30）
            double[] ensemble = new double[forecastDays];
            for (int i = 0; i < forecastDays; i++) {
                ensemble[i] = arimaForecast[i] * 0.35 + hwForecast[i] * 0.35 + linearForecast[i] * 0.30;
                ensemble[i] = Math.max(0, Math.min(100, ensemble[i]));
            }

            // 趨勢判斷
            double currentVal = data[data.length - 1];
            String arimaTrend = judgeTrend(currentVal, arimaForecast[arimaForecast.length - 1]);
            String hwTrend = judgeTrend(currentVal, hwForecast[hwForecast.length - 1]);
            String linearTrend = judgeTrend(currentVal, linearForecast[linearForecast.length - 1]);
            String consensusTrend = consensusTrend(arimaTrend, hwTrend, linearTrend);

            result.put(industry, new ProsperityForecastDto.IndustryForecast(
                    industry,
                    toList(arimaForecast),
                    toList(hwForecast),
                    toList(linearForecast),
                    toList(ensemble),
                    Math.round(currentVal * 100.0) / 100.0,
                    arimaTrend,
                    hwTrend,
                    linearTrend,
                    consensusTrend,
                    forecastDates
            ));
        }

        // 找共識上升最多的行業
        List<Map.Entry<String, ProsperityForecastDto.IndustryForecast>> sorted = new ArrayList<>(result.entrySet());
        sorted.sort((a, b) -> {
            double aDelta = a.getValue().ensembleForecast().get(forecastDays - 1) - a.getValue().currentProsperity();
            double bDelta = b.getValue().ensembleForecast().get(forecastDays - 1) - b.getValue().currentProsperity();
            return Double.compare(bDelta, aDelta);
        });

        String summary = String.format(
                "分析區間 %s ~ %s，預測未來 %d 日，%d 個行業。" +
                "共識上升最強：%s（%s）。共識下降最強：%s（%s）。",
                start, end, forecastDays, result.size(),
                sorted.isEmpty() ? "無" : sorted.get(0).getKey(),
                sorted.isEmpty() ? "" : sorted.get(0).getValue().consensusTrend(),
                sorted.isEmpty() ? "無" : sorted.get(sorted.size() - 1).getKey(),
                sorted.isEmpty() ? "" : sorted.get(sorted.size() - 1).getValue().consensusTrend()
        );

        return new ProsperityForecastDto(end.toString(), forecastDays, result, summary);
    }

    /** ARIMA 簡化版預測：AR(2) + 一階差分。 */
    private double[] forecastARIMA(double[] data, int steps) {
        int n = data.length;
        if (n < 4) {
            double last = n > 0 ? data[n - 1] : 50.0;
            double[] result = new double[steps];
            for (int i = 0; i < steps; i++) result[i] = last;
            return result;
        }

        // 一階差分
        double[] diff = new double[n - 1];
        for (int i = 0; i < n - 1; i++) {
            diff[i] = data[i + 1] - data[i];
        }

        // AR(2) on differenced data: diff[t] = a*diff[t-1] + b*diff[t-2] + c
        // 用最小二乘法估計 a, b, c
        double[] ar2 = fitAR2(diff);

        // 預測差分
        double[] forecastDiff = new double[steps];
        double prevDiff1 = diff[diff.length - 1];
        double prevDiff2 = diff.length > 1 ? diff[diff.length - 2] : 0;
        for (int i = 0; i < steps; i++) {
            forecastDiff[i] = ar2[0] * prevDiff1 + ar2[1] * prevDiff2 + ar2[2];
            prevDiff2 = prevDiff1;
            prevDiff1 = forecastDiff[i];
        }

        // 反差分還原
        double[] forecast = new double[steps];
        double lastVal = data[n - 1];
        for (int i = 0; i < steps; i++) {
            lastVal += forecastDiff[i];
            forecast[i] = Math.max(0, Math.min(100, lastVal));
        }
        return forecast;
    }

    /** AR(2) 係數估計（最小二乘法）。 */
    private double[] fitAR2(double[] data) {
        int n = data.length;
        if (n < 4) return new double[]{0, 0, 0};

        // 構建回歸矩陣: y = X * beta
        // y[i] = data[i+2], X[i] = [data[i+1], data[i], 1]
        int m = n - 2;
        double[][] X = new double[m][3];
        double[] y = new double[m];
        for (int i = 0; i < m; i++) {
            X[i][0] = data[i + 1];
            X[i][1] = data[i];
            X[i][2] = 1;
            y[i] = data[i + 2];
        }

        // 正規方程: beta = (X^T X)^-1 X^T y
        // X^T X (3x3)
        double[][] XtX = new double[3][3];
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 3; j++) {
                for (int k = 0; k < m; k++) {
                    XtX[i][j] += X[k][i] * X[k][j];
                }
            }
        }
        // X^T y (3x1)
        double[] Xty = new double[3];
        for (int i = 0; i < 3; i++) {
            for (int k = 0; k < m; k++) {
                Xty[i] += X[k][i] * y[k];
            }
        }
        // 解 3x3 線性方程組（高斯消去法）
        return solveLinearSystem(XtX, Xty);
    }

    /** Holt-Winters 三重指數平滑預測。 */
    private double[] forecastHoltWinters(double[] data, int steps, int seasonLength) {
        int n = data.length;
        if (n < seasonLength * 2) {
            // 數據不足，用簡單移動平均
            double avg = 0;
            int lookback = Math.min(5, n);
            for (int i = n - lookback; i < n; i++) avg += data[i];
            avg /= lookback;
            double[] result = new double[steps];
            for (int i = 0; i < steps; i++) result[i] = avg;
            return result;
        }

        double alpha = 0.3; // 水平平滑係數
        double beta = 0.1;  // 趨勢平滑係數
        double gamma = 0.2; // 季節平滑係數

        // 初始化
        double level = 0;
        for (int i = 0; i < seasonLength; i++) level += data[i];
        level /= seasonLength;

        double trend = 0;
        for (int i = 0; i < seasonLength; i++) {
            trend += (data[seasonLength + i] - data[i]);
        }
        trend /= seasonLength;

        double[] seasonals = new double[seasonLength];
        for (int i = 0; i < seasonLength; i++) {
            seasonals[i] = data[i] - level;
        }

        // 迭代更新
        for (int i = seasonLength; i < n; i++) {
            double val = data[i];
            double lastLevel = level;
            int seasonIdx = i % seasonLength;

            level = alpha * (val - seasonals[seasonIdx]) + (1 - alpha) * (level + trend);
            trend = beta * (level - lastLevel) + (1 - beta) * trend;
            seasonals[seasonIdx] = gamma * (val - level) + (1 - gamma) * seasonals[seasonIdx];
        }

        // 預測
        double[] forecast = new double[steps];
        for (int i = 0; i < steps; i++) {
            int seasonIdx = (n + i) % seasonLength;
            forecast[i] = Math.max(0, Math.min(100, level + (i + 1) * trend + seasonals[seasonIdx]));
        }
        return forecast;
    }

    /** 線性回歸預測（OLS）。 */
    private double[] forecastLinearRegression(double[] data, int steps) {
        int n = data.length;
        if (n < 3) {
            double last = n > 0 ? data[n - 1] : 50.0;
            double[] result = new double[steps];
            for (int i = 0; i < steps; i++) result[i] = last;
            return result;
        }

        // OLS: y = a + b * x
        double sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        for (int i = 0; i < n; i++) {
            sumX += i;
            sumY += data[i];
            sumXY += i * data[i];
            sumX2 += (double) i * i;
        }
        double meanX = sumX / n;
        double meanY = sumY / n;

        double b = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
        double a = meanY - b * meanX;

        // 預測
        double[] forecast = new double[steps];
        for (int i = 0; i < steps; i++) {
            forecast[i] = Math.max(0, Math.min(100, a + b * (n + i)));
        }
        return forecast;
    }

    /**
     * 行業景氣度預測回測 — 驗證多模型預測的歷史準確率。
     *
     * 回測邏輯：
     * 1. 對每個歷史交易日 T，用 T 之前的數據預測 T+forecastDays 的景氣度
     * 2. 比較預測值與實際景氣度
     * 3. 計算 MAE、方向準確率、等級命中率、超額收益
     *
     * @param months        分析回溯月數（默認 6）
     * @param forecastDays  預測天數（默認 5）
     * @param backtestDays  回測總天數（默認 60）
     * @return 回測結果 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'forecast-backtest-' + #p0 + '-' + #p1 + '-' + #p2")
    public ProsperityForecastBacktestDto prosperityForecastBacktest(int months, int forecastDays, int backtestDays) {
        LocalDate today = LocalDate.now();
        LocalDate dataStart = today.minusMonths(months).minusDays(backtestDays + 20);
        LocalDate dataEnd = today;

        List<IndustryDailyEntity> allEntities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(dataStart, dataEnd);

        if (allEntities.isEmpty()) {
            return new ProsperityForecastBacktestDto(forecastDays, 0, 0, 0, 0, 0, 0, 0,
                    "數據不足，無法回測", List.of());
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : allEntities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < forecastDays + 10) {
            return new ProsperityForecastBacktestDto(forecastDays, 0, 0, 0, 0, 0, 0, 0,
                    "交易日不足，無法回測", List.of());
        }

        // 預計算每日景氣度
        Map<LocalDate, Map<String, Double>> dailyProsperity = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            dailyProsperity.put(date, computeProsperityMap(byDate.get(date)));
        }

        // 回測窗口
        int startIdx = Math.max(20, sortedDates.size() - backtestDays - forecastDays);
        int endIdx = sortedDates.size() - forecastDays;

        List<ProsperityForecastBacktestDto.BacktestEntry> entries = new ArrayList<>();
        double totalAbsError = 0;
        int directionCorrect = 0;
        int gradeCorrect = 0;
        double totalTopReturn = 0;
        double totalMarketReturn = 0;

        // 每隔幾個交易日取樣一次
        int step = Math.max(1, (endIdx - startIdx) / 20);

        for (int i = startIdx; i < endIdx; i += step) {
            LocalDate predictDate = sortedDates.get(i);
            LocalDate targetDate = sortedDates.get(Math.min(i + forecastDays, sortedDates.size() - 1));

            // 用 predictDate 之前的數據預測
            Map<String, List<Double>> industrySeries = new LinkedHashMap<>();
            for (int j = Math.max(0, i - months * 21); j <= i; j++) {
                Map<String, Double> dp = dailyProsperity.get(sortedDates.get(j));
                for (Map.Entry<String, Double> e : dp.entrySet()) {
                    industrySeries.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(e.getValue());
                }
            }

            // 對每個行業預測景氣度
            Map<String, Double> predictedProsperity = new LinkedHashMap<>();
            for (Map.Entry<String, List<Double>> entry : industrySeries.entrySet()) {
                double[] data = entry.getValue().stream().mapToDouble(Double::doubleValue).toArray();
                if (data.length < 10) continue;

                double[] arimaF = forecastARIMA(data, forecastDays);
                double[] hwF = forecastHoltWinters(data, forecastDays, 5);
                double[] linearF = forecastLinearRegression(data, forecastDays);

                double ensemble = arimaF[arimaF.length - 1] * 0.35
                        + hwF[hwF.length - 1] * 0.35 + linearF[linearF.length - 1] * 0.30;
                predictedProsperity.put(entry.getKey(), Math.max(0, Math.min(100, ensemble)));
            }

            if (predictedProsperity.isEmpty()) continue;

            // 實際景氣度
            Map<String, Double> actualProsperity = dailyProsperity.getOrDefault(targetDate, Map.of());
            if (actualProsperity.isEmpty()) continue;

            // 找預測 Top 1 和實際 Top 1
            String topPredicted = predictedProsperity.entrySet().stream()
                    .max(Map.Entry.comparingByValue()).map(Map.Entry::getKey).orElse("");
            String topActual = actualProsperity.entrySet().stream()
                    .max(Map.Entry.comparingByValue()).map(Map.Entry::getKey).orElse("");

            double predictedVal = predictedProsperity.getOrDefault(topPredicted, 0.0);
            double actualVal = actualProsperity.getOrDefault(topPredicted, 0.0);
            double absError = Math.abs(predictedVal - actualVal);

            // 方向準確率：預測的上升/下降方向是否正確
            double prevVal = dailyProsperity.get(predictDate).getOrDefault(topPredicted, 50.0);
            boolean predictedUp = predictedVal > prevVal;
            boolean actualUp = actualVal > prevVal;
            boolean dirCorrect = predictedUp == actualUp;
            if (dirCorrect) directionCorrect++;

            // 等級命中率
            String predictedGrade = prosperityGrade(predictedVal);
            String actualGrade = prosperityGrade(actualVal);
            boolean gCorrect = predictedGrade.equals(actualGrade);
            if (gCorrect) gradeCorrect++;

            totalAbsError += absError;

            // 超額收益：預測 Top 行業在 predictDate → targetDate 的實際漲跌幅
            double topReturn = 0;
            List<IndustryDailyEntity> predictDayEntities = byDate.get(predictDate);
            List<IndustryDailyEntity> targetDayEntities = byDate.get(targetDate);
            if (predictDayEntities != null && targetDayEntities != null) {
                double predictPct = predictDayEntities.stream()
                        .filter(e -> topPredicted.equals(e.getIndustry()))
                        .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0)
                        .findFirst().orElse(0);
                double targetPct = targetDayEntities.stream()
                        .filter(e -> topPredicted.equals(e.getIndustry()))
                        .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0)
                        .findFirst().orElse(0);
                topReturn = targetPct - predictPct;

                double marketPct = predictDayEntities.stream()
                        .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0)
                        .average().orElse(0);
                double marketTargetPct = targetDayEntities.stream()
                        .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0)
                        .average().orElse(0);
                double marketReturn = marketTargetPct - marketPct;
                totalMarketReturn += marketReturn;
            }
            totalTopReturn += topReturn;

            entries.add(new ProsperityForecastBacktestDto.BacktestEntry(
                    predictDate.toString(),
                    targetDate.toString(),
                    topPredicted,
                    topActual,
                    Math.round(predictedVal * 100.0) / 100.0,
                    Math.round(actualVal * 100.0) / 100.0,
                    Math.round(absError * 100.0) / 100.0,
                    dirCorrect,
                    gCorrect
            ));
        }

        int total = entries.size();
        double mae = total > 0 ? totalAbsError / total : 0;
        double dirAcc = total > 0 ? (double) directionCorrect / total * 100.0 : 0;
        double gradeHit = total > 0 ? (double) gradeCorrect / total * 100.0 : 0;
        double avgTop = total > 0 ? totalTopReturn / total : 0;
        double avgMarket = total > 0 ? totalMarketReturn / total : 0;
        double avgExcess = avgTop - avgMarket;

        String summary = String.format(
                "回測 %d 次（forecast=%d日）。MAE %.2f，方向準確率 %.1f%%，等級命中率 %.1f%%。" +
                "預測 Top 行業平均收益 %.3f%%，市場平均 %.3f%%，超額收益 %.3f%%。",
                total, forecastDays, mae, dirAcc, gradeHit, avgTop, avgMarket, avgExcess
        );

        return new ProsperityForecastBacktestDto(
                forecastDays, total,
                Math.round(mae * 100.0) / 100.0,
                Math.round(dirAcc * 100.0) / 100.0,
                Math.round(gradeHit * 100.0) / 100.0,
                Math.round(avgTop * 1000.0) / 1000.0,
                Math.round(avgMarket * 1000.0) / 1000.0,
                Math.round(avgExcess * 1000.0) / 1000.0,
                summary,
                entries
        );
    }

    /**
     * 行業輪動 Markov 模型 — 預測領漲行業轉換概率。
     *
     * 將行業按每日漲跌幅排名分為 3 個狀態：
     * 1=領漲（Top 1/3）、2=中間（Middle 1/3）、3=滯後（Bottom 1/3）
     *
     * @param lookbackDays 回溯天數（默認 30）
     * @return 輪動 Markov 分析 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'rotation-markov-' + #p0")
    public RotationMarkovDto rotationMarkov(int lookbackDays) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusDays(lookbackDays + 10);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new RotationMarkovDto(end.toString(), 0, Map.of(), "數據不足，無法構建輪動 Markov 模型");
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < 3) {
            return new RotationMarkovDto(end.toString(), 0, Map.of(), "交易日不足，無法構建輪動 Markov 模型");
        }

        // 每日按漲跌幅排名，分為 3 個狀態
        Map<LocalDate, Map<String, Integer>> dailyStates = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            List<IndustryDailyEntity> dayEntities = byDate.get(date);
            // 按漲跌幅排序
            List<IndustryDailyEntity> sorted = new ArrayList<>(dayEntities);
            sorted.sort((a, b) -> {
                double aPct = a.getAvgPctChg() != null ? a.getAvgPctChg().doubleValue() : 0;
                double bPct = b.getAvgPctChg() != null ? b.getAvgPctChg().doubleValue() : 0;
                return Double.compare(bPct, aPct); // 倒序
            });

            int n = sorted.size();
            int topThird = n / 3;
            int midThird = n * 2 / 3;

            Map<String, Integer> states = new LinkedHashMap<>();
            for (int i = 0; i < n; i++) {
                int state;
                if (i < topThird) state = 1; // 領漲
                else if (i < midThird) state = 2; // 中間
                else state = 3; // 滯後
                states.put(sorted.get(i).getIndustry(), state);
            }
            dailyStates.put(date, states);
        }

        // 按行業收集狀態序列
        Map<String, List<Integer>> industryStateSeries = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            Map<String, Integer> states = dailyStates.get(date);
            for (Map.Entry<String, Integer> e : states.entrySet()) {
                industryStateSeries.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(e.getValue());
            }
        }

        Map<String, RotationMarkovDto.IndustryRotationMarkov> result = new LinkedHashMap<>();
        int totalTransitions = 0;

        for (Map.Entry<String, List<Integer>> entry : industryStateSeries.entrySet()) {
            String industry = entry.getKey();
            List<Integer> series = entry.getValue();
            if (series.size() < 3) continue;

            // 構建 3x3 轉移計數矩陣
            int[][] counts = new int[3][3];
            for (int i = 0; i < series.size() - 1; i++) {
                int from = series.get(i) - 1;
                int to = series.get(i + 1) - 1;
                if (from >= 0 && from < 3 && to >= 0 && to < 3) {
                    counts[from][to]++;
                    totalTransitions++;
                }
            }

            // 轉為概率矩陣
            double[][] matrix = new double[3][3];
            for (int i = 0; i < 3; i++) {
                int rowSum = 0;
                for (int j = 0; j < 3; j++) rowSum += counts[i][j];
                for (int j = 0; j < 3; j++) {
                    matrix[i][j] = rowSum > 0 ? (double) counts[i][j] / rowSum : 0.0;
                    matrix[i][j] = Math.round(matrix[i][j] * 10000.0) / 10000.0;
                }
                if (rowSum == 0) {
                    for (int j = 0; j < 3; j++) matrix[i][j] = 1.0 / 3;
                }
            }

            int currentState = series.get(series.size() - 1);
            String currentStateName = rotationStateName(currentState);

            // 下一期各狀態概率
            Map<Integer, Double> nextProb = new LinkedHashMap<>();
            int currentIdx = currentState - 1;
            for (int j = 0; j < 3; j++) {
                nextProb.put(j + 1, matrix[currentIdx][j]);
            }

            // 最可能下一狀態
            int mostLikelyNext = 1;
            double mostLikelyProb = 0;
            for (int j = 0; j < 3; j++) {
                if (matrix[currentIdx][j] > mostLikelyProb) {
                    mostLikelyProb = matrix[currentIdx][j];
                    mostLikelyNext = j + 1;
                }
            }

            // 穩態分布（3x3 迭代）
            Map<Integer, Double> steadyState = computeSteadyState3(matrix);
            double leaderProb = steadyState.getOrDefault(1, 0.0);

            int transitionCount = 0;
            for (int i = 0; i < 3; i++) {
                for (int j = 0; j < 3; j++) transitionCount += counts[i][j];
            }

            result.put(industry, new RotationMarkovDto.IndustryRotationMarkov(
                    industry,
                    matrix,
                    currentState,
                    currentStateName,
                    nextProb,
                    steadyState,
                    transitionCount,
                    rotationStateName(mostLikelyNext),
                    Math.round(mostLikelyProb * 1000.0) / 1000.0,
                    Math.round(leaderProb * 10000.0) / 10000.0
            ));
        }

        // 找長期領漲概率最高的行業
        List<Map.Entry<String, RotationMarkovDto.IndustryRotationMarkov>> sortedByLeader =
                new ArrayList<>(result.entrySet());
        sortedByLeader.sort((a, b) -> Double.compare(
                b.getValue().leaderProbability(), a.getValue().leaderProbability()));

        String summary = String.format(
                "分析區間 %s ~ %s，共 %d 次狀態轉換，%d 個行業。" +
                "長期領漲概率最高：%s（%.1f%%）。",
                start, end, totalTransitions, result.size(),
                sortedByLeader.isEmpty() ? "無" : sortedByLeader.get(0).getKey(),
                sortedByLeader.isEmpty() ? 0 : sortedByLeader.get(0).getValue().leaderProbability() * 100
        );

        return new RotationMarkovDto(end.toString(), totalTransitions, result, summary);
    }

    /** 輪動狀態名稱。 */
    private static String rotationStateName(int state) {
        return switch (state) {
            case 1 -> "領漲";
            case 2 -> "中間";
            case 3 -> "滯後";
            default -> "未知";
        };
    }

    /** 計算 3x3 Markov 鏈的穩態分布。 */
    private Map<Integer, Double> computeSteadyState3(double[][] matrix) {
        double[] state = {1.0 / 3, 1.0 / 3, 1.0 / 3};
        for (int iter = 0; iter < 1000; iter++) {
            double[] newState = new double[3];
            for (int j = 0; j < 3; j++) {
                for (int i = 0; i < 3; i++) {
                    newState[j] += state[i] * matrix[i][j];
                }
            }
            double maxDiff = 0;
            for (int i = 0; i < 3; i++) {
                maxDiff = Math.max(maxDiff, Math.abs(newState[i] - state[i]));
            }
            System.arraycopy(newState, 0, state, 0, 3);
            if (maxDiff < 1e-8) break;
        }

        Map<Integer, Double> result = new LinkedHashMap<>();
        for (int i = 0; i < 3; i++) {
            result.put(i + 1, Math.round(state[i] * 10000.0) / 10000.0);
        }
        return result;
    }

    /** 判斷趨勢。 */
    private static String judgeTrend(double current, double forecast) {
        double delta = forecast - current;
        if (delta > 3) return "上升";
        if (delta < -3) return "下降";
        return "平穩";
    }

    /** 三模型共識趨勢（多數決）。 */
    private static String consensusTrend(String a, String b, String c) {
        int up = 0, down = 0, flat = 0;
        if ("上升".equals(a)) up++;
        else if ("下降".equals(a)) down++;
        else flat++;
        if ("上升".equals(b)) up++;
        else if ("下降".equals(b)) down++;
        else flat++;
        if ("上升".equals(c)) up++;
        else if ("下降".equals(c)) down++;
        else flat++;

        if (up >= 2) return "上升";
        if (down >= 2) return "下降";
        return "平穩";
    }

    /** 高斯消去法解線性方程組 Ax=b。 */
    private static double[] solveLinearSystem(double[][] A, double[] b) {
        int n = b.length;
        // 增廣矩陣
        double[][] aug = new double[n][n + 1];
        for (int i = 0; i < n; i++) {
            System.arraycopy(A[i], 0, aug[i], 0, n);
            aug[i][n] = b[i];
        }
        // 前向消去
        for (int col = 0; col < n; col++) {
            // 部分選主元
            int maxRow = col;
            for (int row = col + 1; row < n; row++) {
                if (Math.abs(aug[row][col]) > Math.abs(aug[maxRow][col])) {
                    maxRow = row;
                }
            }
            double[] tmp = aug[col];
            aug[col] = aug[maxRow];
            aug[maxRow] = tmp;

            if (Math.abs(aug[col][col]) < 1e-12) continue; // 奇異

            for (int row = col + 1; row < n; row++) {
                double factor = aug[row][col] / aug[col][col];
                for (int j = col; j <= n; j++) {
                    aug[row][j] -= factor * aug[col][j];
                }
            }
        }
        // 回代
        double[] x = new double[n];
        for (int i = n - 1; i >= 0; i--) {
            x[i] = aug[i][n];
            for (int j = i + 1; j < n; j++) {
                x[i] -= aug[i][j] * x[j];
            }
            if (Math.abs(aug[i][i]) > 1e-12) {
                x[i] /= aug[i][i];
            }
        }
        return x;
    }

    /** double[] 轉 List<Double>（四捨五入到小數點 2 位）。 */
    private static List<Double> toList(double[] arr) {
        List<Double> list = new ArrayList<>(arr.length);
        for (double v : arr) {
            list.add(Math.round(v * 100.0) / 100.0);
        }
        return list;
    }

    /** 計算指定日期列表的景氣度 Map（industry -> prosperityIndex）。 */
    private Map<String, Double> computeProsperityMap(List<IndustryDailyEntity> entities) {
        if (entities == null || entities.isEmpty()) return Map.of();

        double[] pctArr = entities.stream()
                .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0)
                .toArray();
        double[] amtArr = entities.stream()
                .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                .toArray();
        double[] turnArr = entities.stream()
                .mapToDouble(e -> e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0)
                .toArray();

        double pctMin = min(pctArr), pctMax = max(pctArr);
        double amtMin = min(amtArr), amtMax = max(amtArr);
        double turnMin = min(turnArr), turnMax = max(turnArr);

        double totalRising = entities.stream()
                .mapToDouble(e -> e.getRisingCount() != null ? e.getRisingCount().doubleValue() : 0.0)
                .sum();
        double totalFalling = entities.stream()
                .mapToDouble(e -> e.getFallingCount() != null ? e.getFallingCount().doubleValue() : 0.0)
                .sum();
        double breadthBase = totalRising + totalFalling;

        Map<String, Double> result = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            double pctChg = e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0;
            double amount = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
            double turn = e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0;
            double rising = e.getRisingCount() != null ? e.getRisingCount().doubleValue() : 0.0;
            double falling = e.getFallingCount() != null ? e.getFallingCount().doubleValue() : 0.0;
            double breadth = breadthBase > 0 ? (rising + (breadthBase - falling)) / breadthBase * 50.0 : 50.0;

            double momentumScore = normalize(pctChg, pctMin, pctMax);
            double capitalScore = normalize(amount, amtMin, amtMax);
            double activityScore = normalize(turn, turnMin, turnMax);
            double breadthScore = normalize(breadth, 0, 100);

            double prosperityIndex = momentumScore * 0.35 + capitalScore * 0.25
                    + activityScore * 0.20 + breadthScore * 0.20;
            result.put(e.getIndustry(), prosperityIndex);
        }
        return result;
    }

    /** 景氣度等級。 */
    private static String prosperityGrade(double prosperityIndex) {
        if (prosperityIndex >= 80) return "繁榮";
        if (prosperityIndex >= 65) return "景氣";
        if (prosperityIndex >= 50) return "平穩";
        if (prosperityIndex >= 35) return "低迷";
        return "衰退";
    }

    /** 等級數值化（越高越好）。 */
    private static int gradeLevel(String grade) {
        return switch (grade) {
            case "繁榮" -> 5;
            case "景氣" -> 4;
            case "平穩" -> 3;
            case "低迷" -> 2;
            case "衰退" -> 1;
            default -> 0;
        };
    }

    /** 嚴重程度排序值。 */
    private static int severityRank(String severity) {
        return switch (severity) {
            case "high" -> 3;
            case "medium" -> 2;
            case "low" -> 1;
            default -> 0;
        };
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
