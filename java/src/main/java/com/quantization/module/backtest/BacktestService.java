package com.quantization.module.backtest;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.quantization.module.backtest.dto.BacktestConfigDto;
import com.quantization.module.backtest.dto.BacktestRequestDto;
import com.quantization.module.backtest.dto.BacktestResultDto;
import com.quantization.module.backtest.dto.BacktestResultDto.BacktestStatistics;
import com.quantization.module.backtest.dto.BacktestResultDto.EquityPoint;
import com.quantization.module.backtest.dto.BacktestResultDto.RebalanceEvent;
import com.quantization.module.backtest.dto.SavedStrategySummaryDto;
import com.quantization.module.backtest.dto.WalkForwardConfigDto;
import com.quantization.module.backtest.dto.WalkForwardResultDto;
import com.quantization.module.screener.ScreenerCore;
import com.quantization.module.screener.ScreenerService;
import com.quantization.module.screener.dto.ScreenedStockDto;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import com.quantization.module.stock.IndexDailyEntity;
import com.quantization.module.stock.StockDaily;
import com.quantization.module.stock.StockService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 回测服务（忠实移植原 Python BacktestService.run_backtest 的等权调仓逻辑）。
 * 策略：每个调仓日按选股条件选出的前 N 只股票等权持有，持有期内不调仓；
 * 基准：等权持有全市场可交易股票（与原版一致）。
 *
 * 增强功能：
 * <ul>
 *   <li>夏普比率扣除无风险利率（{@code riskFreeRate}，默认 0.02）</li>
 *   <li>买卖成交价计入滑点（{@code slippageBps}，默认 0）</li>
 *   <li>调仓选股跳过当日涨停（pctChg &gt;= 9.9）/跌停（pctChg &lt;= -9.9）股票</li>
 *   <li>止损卖出遇跌停（pctChg &lt;= -9.9）延后到下一交易日</li>
 *   <li>{@code runBacktest} 结果自动落库（source=auto）</li>
 * </ul>
 */
@Service
public class BacktestService {

    private static final Logger log = LoggerFactory.getLogger(BacktestService.class);

    private final StockService stockService;
    private final ScreenerCore screenerCore;
    private final BacktestStrategyRepository strategyRepository;
    private final ObjectMapper objectMapper;

    /** 默认基准指数：上证综指（可通过 BacktestConfigDto.benchmarkCode 覆盖）。 */
    private static final String DEFAULT_BENCHMARK_CODE = "sh.000001";

    /** 涨跌停阈值：主板 9.9%，科创板/创业板 19.9%，ST 4.9%。 */
    private static final double LIMIT_THRESHOLD_MAIN = 9.9;
    private static final double LIMIT_THRESHOLD_STAR_CHINEXT = 19.9;
    private static final double LIMIT_THRESHOLD_ST = 4.9;

    public BacktestService(StockService stockService, ScreenerCore screenerCore,
                           BacktestStrategyRepository strategyRepository, ObjectMapper objectMapper) {
        this.stockService = stockService;
        this.screenerCore = screenerCore;
        this.strategyRepository = strategyRepository;
        this.objectMapper = objectMapper;
    }

    /** 根据股票代码推断板块并返回对应的涨跌停阈值。 */
    private double limitThreshold(String code) {
        if (code == null) return LIMIT_THRESHOLD_MAIN;
        // 科创板: sh.688xxx
        if (code.startsWith("sh.688")) return LIMIT_THRESHOLD_STAR_CHINEXT;
        // 创业板: sz.300xxx
        if (code.startsWith("sz.300")) return LIMIT_THRESHOLD_STAR_CHINEXT;
        // ST 股：通过 isSt 字段判断，但此处只能用代码前缀做保守估计
        // 精确判断需要 StockDailyEntity.isSt，在调用处传入
        return LIMIT_THRESHOLD_MAIN;
    }

    /** 根据股票代码和 isSt 标志返回对应的涨跌停阈值。 */
    private double limitThreshold(String code, int isSt) {
        if (isSt == 1) return LIMIT_THRESHOLD_ST;
        return limitThreshold(code);
    }

    /**
     * 执行回测：按选股条件在调仓日选股，等权持有，持有期内不调仓；
     * 基准可配置（默认上证综指 sh.000001），以初始资金为起点按指数涨幅累计。
     * 回测结果会自动落库（source=auto，best-effort，失败不影响结果返回）。
     *
     * @param request 回测请求（含选股条件和回测配置）
     * @return 回测结果（含净值曲线、调仓事件和统计指标）
     */
    @Transactional
    public BacktestResultDto runBacktest(BacktestRequestDto request) {
        ScreenerCriteriaDto criteria = request.criteria();
        BacktestConfigDto config = request.config();
        LocalDate start = config.startDate();
        LocalDate end = config.endDate();
        int rebalanceInterval = Math.max(1, config.effectiveRebalanceInterval());
        int holdingPeriod = Math.max(1, config.effectiveHoldingPeriod());
        int maxPositions = Math.max(1, config.effectiveMaxPositions());
        double initialCapital = config.initialCapital();
        double commissionRate = config.effectiveCommissionBps() / 10000.0;
        double slippageRate = config.effectiveSlippageBps() / 10000.0;
        double riskFreeRate = config.effectiveRiskFreeRate();
        Double stopLoss = config.effectiveStopLossPct();
        Double takeProfit = config.takeProfitPct();
        int executionDelay = config.effectiveExecutionDelay();
        String benchmarkCode = config.effectiveBenchmarkCode();
        Double maxVolumePct = config.effectiveMaxVolumePct();

        // 拉取行情數據：為減少內存壓力，按調倉日分批載入。
        // 策略：只載入每個調倉日前後 LOOKBACK 天的數據（指標最多需 120 天），
        // 而非整個回測區間的全部數據。
        int adjustflag = criteria.adjustflag() != null ? criteria.adjustflag() : 3;

        // 先取得交易日列表
        List<LocalDate> tradeDates = stockService.tradeDates(start, end, adjustflag);
        if (tradeDates.isEmpty()) {
            return saveAndReturn(emptyResult(config, "区间内无交易日。"), request);
        }

        // 調倉日列表
        Set<LocalDate> rebalanceDateSet = new HashSet<>();
        List<LocalDate> rebalanceDateList = new ArrayList<>();
        for (int i = 0; i < tradeDates.size(); i += rebalanceInterval) {
            rebalanceDateSet.add(tradeDates.get(i));
            rebalanceDateList.add(tradeDates.get(i));
        }

        // 交易日索引：用 Map 加速查找
        Map<LocalDate, Integer> tradeDateIndex = new HashMap<>();
        for (int i = 0; i < tradeDates.size(); i++) {
            tradeDateIndex.put(tradeDates.get(i), i);
        }

        // 分批載入數據：對每個調倉日，只載入該日前 150 天的數據
        // 合併所有調倉日的數據需求，取最早的 dataStart
        LocalDate dataStart = start.minusDays(ScreenerService.SCREENING_LOOKBACK_DAYS);
        // 優化：如果回測區間超過 6 個月，分批載入；否則一次載入
        long totalDays = java.time.temporal.ChronoUnit.DAYS.between(start, end);
        ScreenerCore.Grouped grouped;
        Map<String, Map<LocalDate, Double>> priceLookup;
        Map<String, Map<LocalDate, Double>> pctChangeLookup;

        if (totalDays > 180) {
            // 大範圍回測：只載入調倉日附近的數據（每個調倉日前 150 天）
            // 為簡化實現，仍載入全部數據但限制日期範圍為 dataStart 到 end
            // 真正的分批載入需要重構 screenAt，這裡先保持正確性
            List<StockDaily> records = stockService.domainRecordsInRange(dataStart, end, adjustflag, null);
            if (records.isEmpty()) {
                return saveAndReturn(emptyResult(config, "未读取到任何行情数据。"), request);
            }
            grouped = screenerCore.groupHistories(records);
            priceLookup = buildPriceLookup(grouped);
            pctChangeLookup = buildPctChangeLookup(grouped);
        } else {
            // 小範圍回測：一次載入
            List<StockDaily> records = stockService.domainRecordsInRange(dataStart, end, adjustflag, null);
            if (records.isEmpty()) {
                return saveAndReturn(emptyResult(config, "未读取到任何行情数据。"), request);
            }
            grouped = screenerCore.groupHistories(records);
            priceLookup = buildPriceLookup(grouped);
            pctChangeLookup = buildPctChangeLookup(grouped);
        }

        Map<String, String> industryMap = buildIndustryMap(criteria.industries(), grouped.histories().keySet());

        // 拉取基準指數數據（可配置，默認上證綜指）
        List<IndexDailyEntity> indexData = stockService
                .findIndexDailyBetween(benchmarkCode, start, end);
        Map<LocalDate, Double> indexCloseMap = new HashMap<>();
        Double firstIndexClose = null;
        for (IndexDailyEntity idx : indexData) {
            if (idx.getClosePrice() != null) {
                indexCloseMap.put(idx.getTradeDate(), idx.getClosePrice().doubleValue());
                if (firstIndexClose == null) firstIndexClose = idx.getClosePrice().doubleValue();
            }
        }
        final double benchmarkBase = firstIndexClose != null ? firstIndexClose : 1.0;

        // 持仓状态：code -> entryDate, entryPrice, shares, entryDateIndex
        Map<String, Position> positions = new HashMap<>();
        double strategyEquity = initialCapital;
        double benchmarkEquity = initialCapital;
        List<EquityPoint> strategyCurve = new ArrayList<>();
        List<EquityPoint> benchmarkCurve = new ArrayList<>();
        List<EquityPoint> excessCurve = new ArrayList<>();
        List<RebalanceEvent> rebalances = new ArrayList<>();
        int totalTrades = 0;

        for (int dateIdx = 0; dateIdx < tradeDates.size(); dateIdx++) {
            LocalDate date = tradeDates.get(dateIdx);

            // 止损/止盈检查（持有期内）
            // 跌停（pctChg <= -9.9）时无法卖出，延后到下一交易日
            List<String> toExit = new ArrayList<>();
            for (var e : positions.entrySet()) {
                Position p = e.getValue();
                Double price = priceLookup.getOrDefault(e.getKey(), Map.of()).get(date);
                if (price == null) continue;
                if (stopLoss != null && price <= p.entryPrice * (1 - stopLoss / 100.0)) {
                    // 跌停延后：当日跌停则不卖出，留待下一交易日再判断
                    Double pctChg = pctChangeLookup.getOrDefault(e.getKey(), Map.of()).get(date);
                    if (pctChg != null && pctChg <= -limitThreshold(e.getKey())) {
                        continue; // 延后到下一交易日
                    }
                    toExit.add(e.getKey());
                } else if (takeProfit != null && price >= p.entryPrice * (1 + takeProfit / 100.0)) {
                    toExit.add(e.getKey());
                }
            }
            for (String code : toExit) {
                Position p = positions.remove(code);
                Double price = priceLookup.getOrDefault(code, Map.of()).get(date);
                if (price != null && p != null) {
                    // 卖出成交价：下浮滑点
                    double fillPrice = price * (1 - slippageRate);
                    strategyEquity += p.shares * fillPrice * (1 - commissionRate);
                    totalTrades++;
                }
            }

            // 调仓日：检查持有期是否到期，到期则全部平仓并重新选股
            if (rebalanceDateSet.contains(date)) {
                // 平仓到期持仓
                List<String> held = new ArrayList<>(positions.keySet());
                for (String code : held) {
                    Position p = positions.remove(code);
                    if (p == null) continue;
                    // 持有期检查：用預構建的索引計算持有天數（O(1) 而非 O(N)）
                    int heldDays = dateIdx - p.entryDateIndex;
                    if (heldDays >= holdingPeriod) {
                        Double price = priceLookup.getOrDefault(code, Map.of()).get(date);
                        if (price != null) {
                            // 卖出成交价：下浮滑点
                            double fillPrice = price * (1 - slippageRate);
                            strategyEquity += p.shares * fillPrice * (1 - commissionRate);
                            totalTrades++;
                        }
                    } else {
                        positions.put(code, p);
                    }
                }

                // 选股：多取一些候选以备涨跌停过滤后仍有足够标的
                int candidateLimit = Math.max(maxPositions * 3, maxPositions + 10);
                List<ScreenedStockDto> candidates = screenerCore.screenAt(grouped, date, criteria, candidateLimit, industryMap);
                // 涨跌停过滤：按板块动态阈值跳过涨停/跌停股票
                List<ScreenedStockDto> tradable = new ArrayList<>();
                for (ScreenedStockDto c : candidates) {
                    Double pctChg = c.pctChange();
                    if (pctChg != null && Math.abs(pctChg) >= limitThreshold(c.code())) {
                        continue;
                    }
                    tradable.add(c);
                }
                int slots = maxPositions - positions.size();
                List<String> bought = new ArrayList<>();
                // T+1 执行延迟：买入实际在 executionDelay 天后执行
                int execDateIdx = Math.min(dateIdx + executionDelay, tradeDates.size() - 1);
                LocalDate execDate = tradeDates.get(execDateIdx);
                for (int i = 0; i < Math.min(slots, tradable.size()); i++) {
                    String code = tradable.get(i).code();
                    if (positions.containsKey(code)) continue;
                    // T+1: 用执行日的价格成交（若 executionDelay=0 则同日收盘价）
                    Double price = priceLookup.getOrDefault(code, Map.of()).get(execDate);
                    if (price == null || price <= 0) continue;
                    // 买入成交价：上浮滑点
                    double fillPrice = price * (1 + slippageRate);
                    double allocation = strategyEquity / Math.max(1, maxPositions);
                    double shares = allocation / fillPrice;
                    if (shares <= 0) continue;
                    // 流动性约束：单笔买入不超过当日成交量的 maxVolumePct%
                    if (maxVolumePct != null && maxVolumePct > 0) {
                        // TODO: 需要 volumeLookup，暂时跳过流动性检查（maxVolumePct 默认 null）
                    }
                    strategyEquity -= shares * fillPrice * (1 + commissionRate);
                    positions.put(code, new Position(execDate, fillPrice, shares, execDateIdx));
                    bought.add(code);
                    totalTrades++;
                }
                rebalances.add(new RebalanceEvent(date, bought, List.of(), new ArrayList<>(positions.keySet())));
            }

            // 當日估值：精確計算持倉市值（用收盤價估值，不含滑點）
            double holdingsValue = 0;
            for (var e : positions.entrySet()) {
                Double price = priceLookup.getOrDefault(e.getKey(), Map.of()).get(date);
                if (price != null) holdingsValue += e.getValue().shares * price;
            }
            double strategyValue = strategyEquity + holdingsValue;

            // 基準：以初始資金為起點按指數漲幅累計（基準可配置，默認上證綜指）
            Double indexClose = indexCloseMap.get(date);
            if (indexClose != null && benchmarkBase > 0) {
                benchmarkEquity = initialCapital * indexClose / benchmarkBase;
            }

            double excess = strategyValue - benchmarkEquity;
            strategyCurve.add(new EquityPoint(date, strategyValue));
            benchmarkCurve.add(new EquityPoint(date, benchmarkEquity));
            excessCurve.add(new EquityPoint(date, excess));
        }

        BacktestStatistics stats = computeStatistics(strategyCurve, benchmarkCurve, initialCapital,
                rebalances.size(), totalTrades, riskFreeRate);
        List<String> logs = buildLogs(config, tradeDates.size(), rebalances.size(), totalTrades, stats);
        BacktestResultDto result = new BacktestResultDto(config, strategyCurve, benchmarkCurve, excessCurve, rebalances, stats, logs);
        return saveAndReturn(result, request);
    }

    /**
     * Walk-forward 回測：在 train 段運行回測，在 test 段用相同參數驗證樣本外表現。
     *
     * <p>用於評估策略過擬合程度。train 段的 Sharpe 與 test 段的 Sharpe 比值
     * 大於 2 通常表示嚴重過擬合。</p>
     *
     * @param wfConfig walk-forward 配置
     * @return walk-forward 結果（含 train 和 test 段回測結果）
     */
    @Transactional
    public WalkForwardResultDto runWalkForward(WalkForwardConfigDto wfConfig) {
        // 訓練段回測
        BacktestConfigDto trainConfig = new BacktestConfigDto(
                wfConfig.trainStart(), wfConfig.trainEnd(),
                wfConfig.config().rebalanceInterval(), wfConfig.config().holdingPeriod(),
                wfConfig.config().maxPositions(), wfConfig.config().initialCapital(),
                wfConfig.config().commissionBps(), wfConfig.config().stopLossPct(),
                wfConfig.config().takeProfitPct(), wfConfig.config().riskFreeRate(),
                wfConfig.config().slippageBps(), wfConfig.config().executionDelay(),
                wfConfig.config().benchmarkCode(), wfConfig.config().maxVolumePct());
        BacktestRequestDto trainRequest = new BacktestRequestDto(wfConfig.criteria(), trainConfig);
        BacktestResultDto trainResult = runBacktest(trainRequest);

        // 測試段回測（用相同參數，只改日期）
        BacktestConfigDto testConfig = new BacktestConfigDto(
                wfConfig.testStart(), wfConfig.testEnd(),
                wfConfig.config().rebalanceInterval(), wfConfig.config().holdingPeriod(),
                wfConfig.config().maxPositions(), wfConfig.config().initialCapital(),
                wfConfig.config().commissionBps(), wfConfig.config().stopLossPct(),
                wfConfig.config().takeProfitPct(), wfConfig.config().riskFreeRate(),
                wfConfig.config().slippageBps(), wfConfig.config().executionDelay(),
                wfConfig.config().benchmarkCode(), wfConfig.config().maxVolumePct());
        BacktestRequestDto testRequest = new BacktestRequestDto(wfConfig.criteria(), testConfig);
        BacktestResultDto testResult = runBacktest(testRequest);

        // 過擬合評分：train Sharpe / test Sharpe
        double trainSharpe = trainResult.statistics().sharpe();
        double testSharpe = testResult.statistics().sharpe();
        double overfitScore = Math.abs(testSharpe) < 0.01 ? 999 : trainSharpe / testSharpe;

        String summary = String.format(
                "Train: Sharpe=%.2f, Return=%.2f%% | Test: Sharpe=%.2f, Return=%.2f%% | Overfit Score=%.2f%s",
                trainSharpe, trainResult.statistics().totalReturn(),
                testSharpe, testResult.statistics().totalReturn(),
                overfitScore,
                overfitScore > 2 ? " (⚠️ 可能過擬合)" : " (✓ 樣本外表現合理)");

        log.info("Walk-forward 完成: {}", summary);
        return new WalkForwardResultDto(trainResult, testResult, round(overfitScore), summary);
    }

    /**
     * 查询最近 N 次回测记录（按创建时间倒序）。
     *
     * @param limit 返回记录数上限
     * @return 策略摘要列表
     */
    @Transactional(readOnly = true)
    public List<SavedStrategySummaryDto> listRecentRuns(int limit) {
        return strategyRepository.findRecentRuns(limit).stream()
                .map(e -> new SavedStrategySummaryDto(e.getId(), e.getName(), e.getCreatedAt(), e.getUpdatedAt()))
                .toList();
    }

    private record Position(LocalDate entryDate, double entryPrice, double shares, int entryDateIndex) {}

    /** 構建行業對照表：code -> 最新行業名稱 */
    private Map<String, String> buildIndustryMap(List<String> requested, Set<String> codes) {
        if (requested == null || requested.isEmpty() || codes == null || codes.isEmpty()) {
            return Map.of();
        }
        Map<String, String> map = new HashMap<>();
        for (Object[] row : stockService.findLatestIndustriesByCode(new ArrayList<>(codes))) {
            if (row[0] != null && row[1] != null) {
                map.put(row[0].toString(), row[1].toString());
            }
        }
        return map;
    }

    /** 構建 priceLookup：Map<code, Map<date, closePrice>>，O(1) 查找價格 */
    private Map<String, Map<LocalDate, Double>> buildPriceLookup(ScreenerCore.Grouped grouped) {
        Map<String, Map<LocalDate, Double>> lookup = new HashMap<>();
        for (var entry : grouped.histories().entrySet()) {
            Map<LocalDate, Double> datePriceMap = new HashMap<>();
            for (StockDaily r : entry.getValue()) {
                datePriceMap.put(r.tradeDate(), r.closePrice());
            }
            lookup.put(entry.getKey(), datePriceMap);
        }
        return lookup;
    }

    /** 構建 pctChangeLookup：Map<code, Map<date, pctChange>>，O(1) 查找漲跌幅（用於漲跌停判斷） */
    private Map<String, Map<LocalDate, Double>> buildPctChangeLookup(ScreenerCore.Grouped grouped) {
        Map<String, Map<LocalDate, Double>> lookup = new HashMap<>();
        for (var entry : grouped.histories().entrySet()) {
            Map<LocalDate, Double> datePctMap = new HashMap<>();
            for (StockDaily r : entry.getValue()) {
                if (r.pctChange() != null) {
                    datePctMap.put(r.tradeDate(), r.pctChange());
                }
            }
            lookup.put(entry.getKey(), datePctMap);
        }
        return lookup;
    }

    private BacktestStatistics computeStatistics(List<EquityPoint> strategy, List<EquityPoint> benchmark,
                                                 double initialCapital, int rebalanceCount, int totalTrades,
                                                 double riskFreeRate) {
        if (strategy.isEmpty()) {
            return new BacktestStatistics(0, 0, 0, 0, 0, 0, rebalanceCount, totalTrades);
        }
        double finalStrategy = strategy.get(strategy.size() - 1).value();
        double finalBenchmark = benchmark.get(benchmark.size() - 1).value();
        double totalReturn = (finalStrategy / initialCapital - 1) * 100;
        double benchmarkReturn = (finalBenchmark / initialCapital - 1) * 100;
        double excessReturn = totalReturn - benchmarkReturn;
        double days = strategy.size();
        double years = days / 252.0;
        double annualReturn = years > 0 ? (Math.pow(finalStrategy / initialCapital, 1 / years) - 1) * 100 : 0;
        // 最大回撤
        double peak = strategy.get(0).value();
        double maxDrawdown = 0;
        for (EquityPoint p : strategy) {
            peak = Math.max(peak, p.value());
            double dd = (peak - p.value()) / peak * 100;
            maxDrawdown = Math.max(maxDrawdown, dd);
        }
        // 策略日收益率序列
        List<Double> dailyReturns = new ArrayList<>();
        for (int i = 1; i < strategy.size(); i++) {
            double prev = strategy.get(i - 1).value();
            double cur = strategy.get(i).value();
            if (prev > 0) dailyReturns.add(cur / prev - 1);
        }
        // 基準日收益率序列
        List<Double> benchmarkReturns = new ArrayList<>();
        for (int i = 1; i < benchmark.size(); i++) {
            double prev = benchmark.get(i - 1).value();
            double cur = benchmark.get(i).value();
            if (prev > 0) benchmarkReturns.add(cur / prev - 1);
        }
        double mean = dailyReturns.stream().mapToDouble(Double::doubleValue).average().orElse(0);
        double std = Math.sqrt(dailyReturns.stream().mapToDouble(r -> Math.pow(r - mean, 2)).sum() / Math.max(1, dailyReturns.size()));
        double dailyRiskFree = riskFreeRate / 252.0;
        // 夏普比率
        double sharpe = std == 0 ? 0 : (mean - dailyRiskFree) / std * Math.sqrt(252);
        // Sortino Ratio（只懲罰下行波動）
        double downsideStd = Math.sqrt(
            dailyReturns.stream().filter(r -> r < 0)
                .mapToDouble(r -> Math.pow(r - mean, 2)).sum() / Math.max(1, dailyReturns.size()));
        double sortino = downsideStd == 0 ? 0 : (mean - dailyRiskFree) / downsideStd * Math.sqrt(252);
        // Calmar Ratio（年化收益/最大回撤）
        double calmar = maxDrawdown == 0 ? 0 : annualReturn / maxDrawdown;
        // 超額收益序列
        List<Double> excessReturns = new ArrayList<>();
        int minLen = Math.min(dailyReturns.size(), benchmarkReturns.size());
        for (int i = 0; i < minLen; i++) {
            excessReturns.add(dailyReturns.get(i) - benchmarkReturns.get(i));
        }
        double excessMean = excessReturns.stream().mapToDouble(Double::doubleValue).average().orElse(0);
        double trackingError = Math.sqrt(
            excessReturns.stream().mapToDouble(r -> Math.pow(r - excessMean, 2)).sum() / Math.max(1, excessReturns.size()));
        // Information Ratio
        double informationRatio = trackingError == 0 ? 0 : (excessMean / trackingError) * Math.sqrt(252);
        // Beta = cov(strategy, benchmark) / var(benchmark)
        double benchmarkMean = benchmarkReturns.stream().mapToDouble(Double::doubleValue).average().orElse(0);
        double cov = 0, varB = 0;
        for (int i = 0; i < minLen; i++) {
            cov += (dailyReturns.get(i) - mean) * (benchmarkReturns.get(i) - benchmarkMean);
            varB += Math.pow(benchmarkReturns.get(i) - benchmarkMean, 2);
        }
        cov /= Math.max(1, minLen);
        varB /= Math.max(1, minLen);
        double beta = varB == 0 ? 0 : cov / varB;
        // Alpha = 年化策略收益 - beta * 年化基準收益 - 無風險利率
        double annualBenchmarkReturn = years > 0 ? (Math.pow(finalBenchmark / initialCapital, 1 / years) - 1) * 100 : 0;
        double alpha = annualReturn - beta * (annualBenchmarkReturn - riskFreeRate * 100) - riskFreeRate * 100;
        // 勝率（盈利交易日佔比）
        long winDays = dailyReturns.stream().filter(r -> r > 0).count();
        double winRate = dailyReturns.isEmpty() ? 0 : (double) winDays / dailyReturns.size() * 100;
        // 盈虧比（平均盈利/平均虧損）
        double avgWin = dailyReturns.stream().filter(r -> r > 0).mapToDouble(Double::doubleValue).average().orElse(0);
        double avgLoss = dailyReturns.stream().filter(r -> r < 0).mapToDouble(Double::doubleValue).average().orElse(0);
        double profitLossRatio = avgLoss == 0 ? 0 : Math.abs(avgWin / avgLoss);
        // 年化換手率（總交易筆數 / 年數）
        double annualTurnover = years > 0 ? totalTrades / years : 0;
        // Deflated Sharpe（簡化版：假設單次試驗，DSR = Sharpe）
        // 完整版本需要全局試驗計數，此處先用單次試驗近似
        double deflatedSharpe = sharpe;
        int nTrials = 1;
        double pbo = 0;
        return new BacktestStatistics(
                round(totalReturn), round(annualReturn), round(benchmarkReturn), round(excessReturn),
                round(maxDrawdown), round(sharpe), rebalanceCount, totalTrades,
                round(sortino), round(calmar), round(informationRatio), round(beta), round(alpha),
                round(winRate), round(profitLossRatio), round(annualTurnover),
                round(deflatedSharpe), nTrials, round(pbo));
    }

    private double round(double v) {
        return Math.round(v * 100) / 100.0;
    }

    private List<String> buildLogs(BacktestConfigDto config, int tradeDays, int rebalances, int trades, BacktestStatistics stats) {
        return List.of(
                "回测区间：" + config.startDate() + " ~ " + config.endDate() + "，交易日数：" + tradeDays,
                "调仓间隔：" + config.effectiveRebalanceInterval() + " 个交易日，持有期：" + config.effectiveHoldingPeriod() + " 个交易日，最大持仓：" + config.effectiveMaxPositions(),
                "初始资金：" + config.initialCapital() + "，手续费：" + config.effectiveCommissionBps() + " bp，滑点：" + config.effectiveSlippageBps() + " bp，无风险利率：" + config.effectiveRiskFreeRate(),
                "调仓次数：" + rebalances + "，总交易笔数：" + trades,
                "策略总收益：" + stats.totalReturn() + "%，年化：" + stats.annualReturn() + "%",
                "基准收益：" + stats.benchmarkReturn() + "%，超额收益：" + stats.excessReturn() + "%",
                "最大回撤：" + stats.maxDrawdown() + "%，夏普比率：" + stats.sharpe() + "，Sortino：" + stats.sortino() + "，Calmar：" + stats.calmar(),
                "信息比率：" + stats.informationRatio() + "，Beta：" + stats.beta() + "，Alpha：" + stats.alpha(),
                "胜率：" + stats.winRate() + "%，盈亏比：" + stats.profitLossRatio() + "，年化换手率：" + stats.annualTurnover()
        );
    }

    private BacktestResultDto emptyResult(BacktestConfigDto config, String message) {
        return new BacktestResultDto(config, List.of(), List.of(), List.of(), List.of(),
                new BacktestStatistics(0, 0, 0, 0, 0, 0, 0, 0), List.of(message));
    }

    /**
     * 将回测结果自动落库（source=auto，best-effort），并返回原始结果。
     * 落库失败仅记录日志，不影响回测结果返回。
     */
    private BacktestResultDto saveAndReturn(BacktestResultDto result, BacktestRequestDto request) {
        try {
            String criteriaJson = objectMapper.writeValueAsString(request.criteria());
            String configJson = objectMapper.writeValueAsString(result.config());
            String resultJson = objectMapper.writeValueAsString(result);

            BacktestStrategyEntity entity = new BacktestStrategyEntity();
            entity.setName("回测-" + LocalDateTime.now().format(
                    java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss")));
            entity.setCriteriaJson(criteriaJson);
            entity.setConfigJson(configJson);
            entity.setResultJson(resultJson);
            entity.setSource("auto");
            entity.setCreatedAt(LocalDateTime.now());
            entity.setUpdatedAt(LocalDateTime.now());
            strategyRepository.save(entity);
        } catch (Exception e) {
            log.warn("回测结果自动落库失败: {}", e.getMessage());
        }
        return result;
    }
}
