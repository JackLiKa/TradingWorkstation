package com.quantization.module.backtest;

import com.quantization.module.backtest.dto.BacktestConfigDto;
import com.quantization.module.backtest.dto.BacktestRequestDto;
import com.quantization.module.backtest.dto.BacktestResultDto;
import com.quantization.module.backtest.dto.BacktestResultDto.BacktestStatistics;
import com.quantization.module.backtest.dto.BacktestResultDto.EquityPoint;
import com.quantization.module.backtest.dto.BacktestResultDto.RebalanceEvent;
import com.quantization.module.screener.ScreenerCore;
import com.quantization.module.screener.ScreenerService;
import com.quantization.module.screener.dto.ScreenedStockDto;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import com.quantization.module.stock.IndexDailyEntity;
import com.quantization.module.stock.IndexDailyRepository;
import com.quantization.module.stock.StockDaily;
import com.quantization.module.stock.StockService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
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
 */
@Service
@Transactional(readOnly = true)
public class BacktestService {

    private final StockService stockService;
    private final ScreenerCore screenerCore;
    private final IndexDailyRepository indexDailyRepository;

    /** 基準指數：上證綜指 */
    private static final String BENCHMARK_CODE = "sh.000001";

    public BacktestService(StockService stockService, ScreenerCore screenerCore, IndexDailyRepository indexDailyRepository) {
        this.stockService = stockService;
        this.screenerCore = screenerCore;
        this.indexDailyRepository = indexDailyRepository;
    }

    /**
     * 执行回测：按选股条件在调仓日选股，等权持有，持有期内不调仓；
     * 基准为上证综指（sh.000001），以初始资金为起点按指数涨幅累计。
     *
     * @param request 回测请求（含选股条件和回测配置）
     * @return 回测结果（含净值曲线、调仓事件和统计指标）
     */
    public BacktestResultDto runBacktest(BacktestRequestDto request) {
        ScreenerCriteriaDto criteria = request.criteria();
        BacktestConfigDto config = request.config();
        LocalDate start = config.startDate();
        LocalDate end = config.endDate();
        int rebalanceInterval = Math.max(1, config.rebalanceInterval());
        int holdingPeriod = Math.max(1, config.holdingPeriod());
        int maxPositions = Math.max(1, config.maxPositions());
        double initialCapital = config.initialCapital();
        double commissionRate = config.commissionBps() / 10000.0;
        Double stopLoss = config.stopLossPct();
        Double takeProfit = config.takeProfitPct();

        // 拉取行情數據：為減少內存壓力，按調倉日分批載入。
        // 策略：只載入每個調倉日前後 LOOKBACK 天的數據（指標最多需 120 天），
        // 而非整個回測區間的全部數據。
        int adjustflag = criteria.adjustflag() != null ? criteria.adjustflag() : 3;

        // 先取得交易日列表
        List<LocalDate> tradeDates = stockService.tradeDates(start, end, adjustflag);
        if (tradeDates.isEmpty()) {
            return emptyResult(config, "区间内无交易日。");
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

        if (totalDays > 180) {
            // 大範圍回測：只載入調倉日附近的數據（每個調倉日前 150 天）
            // 為簡化實現，仍載入全部數據但限制日期範圍為 dataStart 到 end
            // 真正的分批載入需要重構 screenAt，這裡先保持正確性
            List<StockDaily> records = stockService.domainRecordsInRange(dataStart, end, adjustflag, null);
            if (records.isEmpty()) {
                return emptyResult(config, "未读取到任何行情数据。");
            }
            grouped = screenerCore.groupHistories(records);
            priceLookup = buildPriceLookup(grouped);
        } else {
            // 小範圍回測：一次載入
            List<StockDaily> records = stockService.domainRecordsInRange(dataStart, end, adjustflag, null);
            if (records.isEmpty()) {
                return emptyResult(config, "未读取到任何行情数据。");
            }
            grouped = screenerCore.groupHistories(records);
            priceLookup = buildPriceLookup(grouped);
        }

        // 拉取基準指數（上證綜指）數據
        List<IndexDailyEntity> indexData = indexDailyRepository
                .findByCodeAndTradeDateBetweenOrderByTradeDateAsc(BENCHMARK_CODE, start, end);
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
            List<String> toExit = new ArrayList<>();
            for (var e : positions.entrySet()) {
                Position p = e.getValue();
                Double price = priceLookup.getOrDefault(e.getKey(), Map.of()).get(date);
                if (price == null) continue;
                if (stopLoss != null && price <= p.entryPrice * (1 - stopLoss / 100.0)) {
                    toExit.add(e.getKey());
                } else if (takeProfit != null && price >= p.entryPrice * (1 + takeProfit / 100.0)) {
                    toExit.add(e.getKey());
                }
            }
            for (String code : toExit) {
                Position p = positions.remove(code);
                Double price = priceLookup.getOrDefault(code, Map.of()).get(date);
                if (price != null && p != null) {
                    strategyEquity += p.shares * price * (1 - commissionRate);
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
                            strategyEquity += p.shares * price * (1 - commissionRate);
                            totalTrades++;
                        }
                    } else {
                        positions.put(code, p);
                    }
                }

                // 选股
                List<ScreenedStockDto> candidates = screenerCore.screenAt(grouped, date, criteria, maxPositions);
                int slots = maxPositions - positions.size();
                List<String> bought = new ArrayList<>();
                for (int i = 0; i < Math.min(slots, candidates.size()); i++) {
                    String code = candidates.get(i).code();
                    if (positions.containsKey(code)) continue;
                    Double price = priceLookup.getOrDefault(code, Map.of()).get(date);
                    if (price == null || price <= 0) continue;
                    double allocation = strategyEquity / Math.max(1, maxPositions);
                    double shares = allocation / price;
                    if (shares <= 0) continue;
                    strategyEquity -= shares * price * (1 + commissionRate);
                    positions.put(code, new Position(date, price, shares, dateIdx));
                    bought.add(code);
                    totalTrades++;
                }
                rebalances.add(new RebalanceEvent(date, bought, List.of(), new ArrayList<>(positions.keySet())));
            }

            // 當日估值：精確計算持倉市值
            double holdingsValue = 0;
            for (var e : positions.entrySet()) {
                Double price = priceLookup.getOrDefault(e.getKey(), Map.of()).get(date);
                if (price != null) holdingsValue += e.getValue().shares * price;
            }
            double strategyValue = strategyEquity + holdingsValue;

            // 基準：上證綜指（sh.000001），以初始資金為起點按指數漲幅累計
            Double indexClose = indexCloseMap.get(date);
            if (indexClose != null && benchmarkBase > 0) {
                benchmarkEquity = initialCapital * indexClose / benchmarkBase;
            }

            double excess = strategyValue - benchmarkEquity;
            strategyCurve.add(new EquityPoint(date, strategyValue));
            benchmarkCurve.add(new EquityPoint(date, benchmarkEquity));
            excessCurve.add(new EquityPoint(date, excess));
        }

        BacktestStatistics stats = computeStatistics(strategyCurve, benchmarkCurve, initialCapital, rebalances.size(), totalTrades);
        List<String> logs = buildLogs(config, tradeDates.size(), rebalances.size(), totalTrades, stats);
        return new BacktestResultDto(config, strategyCurve, benchmarkCurve, excessCurve, rebalances, stats, logs);
    }

    private record Position(LocalDate entryDate, double entryPrice, double shares, int entryDateIndex) {}

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

    private BacktestStatistics computeStatistics(List<EquityPoint> strategy, List<EquityPoint> benchmark,
                                                 double initialCapital, int rebalanceCount, int totalTrades) {
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
        // 夏普比率：日收益均值/标准差 * sqrt(252) 年化
        // dailyReturns 已是小數形式（如 0.01 = 1%），無需再乘 100
        List<Double> dailyReturns = new ArrayList<>();
        for (int i = 1; i < strategy.size(); i++) {
            double prev = strategy.get(i - 1).value();
            double cur = strategy.get(i).value();
            if (prev > 0) dailyReturns.add(cur / prev - 1);
        }
        double sharpe = 0;
        if (dailyReturns.size() > 1) {
            double mean = dailyReturns.stream().mapToDouble(Double::doubleValue).average().orElse(0);
            double std = Math.sqrt(dailyReturns.stream().mapToDouble(r -> Math.pow(r - mean, 2)).sum() / dailyReturns.size());
            sharpe = std == 0 ? 0 : mean / std * Math.sqrt(252);
        }
        return new BacktestStatistics(
                round(totalReturn), round(annualReturn), round(benchmarkReturn), round(excessReturn),
                round(maxDrawdown), round(sharpe), rebalanceCount, totalTrades);
    }

    private double round(double v) {
        return Math.round(v * 100) / 100.0;
    }

    private List<String> buildLogs(BacktestConfigDto config, int tradeDays, int rebalances, int trades, BacktestStatistics stats) {
        return List.of(
                "回测区间：" + config.startDate() + " ~ " + config.endDate() + "，交易日数：" + tradeDays,
                "调仓间隔：" + config.rebalanceInterval() + " 个交易日，持有期：" + config.holdingPeriod() + " 个交易日，最大持仓：" + config.maxPositions(),
                "初始资金：" + config.initialCapital() + "，手续费：" + config.commissionBps() + " bp",
                "调仓次数：" + rebalances + "，总交易笔数：" + trades,
                "策略总收益：" + stats.totalReturn() + "%，年化：" + stats.annualReturn() + "%",
                "基准收益：" + stats.benchmarkReturn() + "%，超额收益：" + stats.excessReturn() + "%",
                "最大回撤：" + stats.maxDrawdown() + "%，夏普比率：" + stats.sharpe()
        );
    }

    private BacktestResultDto emptyResult(BacktestConfigDto config, String message) {
        return new BacktestResultDto(config, List.of(), List.of(), List.of(), List.of(),
                new BacktestStatistics(0, 0, 0, 0, 0, 0, 0, 0), List.of(message));
    }
}
