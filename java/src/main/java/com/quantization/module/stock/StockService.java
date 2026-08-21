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
import com.quantization.module.stock.dto.ProsperityAlertDto;
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
