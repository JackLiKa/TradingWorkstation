package com.quantization.module.backtest.dto;

import java.time.LocalDate;

/**
 * 回测配置 DTO，定义回测的时间范围、调仓参数、资金和手续费等。
 *
 * @param startDate        回测起始日期
 * @param endDate          回测结束日期
 * @param rebalanceInterval 调仓间隔（交易日数，默认 5）
 * @param holdingPeriod     持有期（交易日数，默认 10）
 * @param maxPositions      最大持仓数（默认 5）
 * @param initialCapital    初始资金
 * @param commissionBps     手续费（基点，1bp = 0.01%，默认 3）
 * @param stopLossPct       止损百分比（null 表示不启用）
 * @param takeProfitPct     止盈百分比（null 表示不启用）
 * @param riskFreeRate      无风险年化利率（默认 0.02），用于夏普比率计算
 * @param slippageBps       滑点（基点，默认 5），买入价上浮、卖出价下浮
 * @param executionDelay    执行延迟天数（默认 1=T+1，0=T+0）
 * @param benchmarkCode     基准指数代码（默认 sh.000001 上证综指）
 * @param maxVolumePct      单笔买入不超过当日成交量的百分比（null 表示不限制）
 */
public record BacktestConfigDto(
        LocalDate startDate,
        LocalDate endDate,
        int rebalanceInterval,
        int holdingPeriod,
        int maxPositions,
        double initialCapital,
        double commissionBps,
        Double stopLossPct,
        Double takeProfitPct,
        Double riskFreeRate,
        Integer slippageBps,
        Integer executionDelay,
        String benchmarkCode,
        Double maxVolumePct
) {
    /** 默认无风险年化利率。 */
    public static final double DEFAULT_RISK_FREE_RATE = 0.02;
    /** 默认滑点（基点）。 */
    public static final int DEFAULT_SLIPPAGE_BPS = 5;
    /** 默认手续费（基点）。 */
    public static final double DEFAULT_COMMISSION_BPS = 3.0;
    /** 默认调仓间隔（交易日数）。 */
    public static final int DEFAULT_REBALANCE_INTERVAL = 5;
    /** 默认持有期（交易日数）。 */
    public static final int DEFAULT_HOLDING_PERIOD = 10;
    /** 默认最大持仓数。 */
    public static final int DEFAULT_MAX_POSITIONS = 5;
    /** 默认执行延迟（T+1）。 */
    public static final int DEFAULT_EXECUTION_DELAY = 1;
    /** 默认基准指数。 */
    public static final String DEFAULT_BENCHMARK_CODE = "sh.000001";
    /** 默认止损百分比（10%）。 */
    public static final double DEFAULT_STOP_LOSS_PCT = 10.0;

    public BacktestConfigDto {
        if (riskFreeRate == null) riskFreeRate = DEFAULT_RISK_FREE_RATE;
        if (slippageBps == null) slippageBps = DEFAULT_SLIPPAGE_BPS;
        if (executionDelay == null) executionDelay = DEFAULT_EXECUTION_DELAY;
        if (benchmarkCode == null) benchmarkCode = DEFAULT_BENCHMARK_CODE;
    }

    /** 有效无风险年化利率（永不为 null）。 */
    public double effectiveRiskFreeRate() {
        return riskFreeRate == null ? DEFAULT_RISK_FREE_RATE : riskFreeRate;
    }

    /** 有效滑点基点（永不为 null）。 */
    public int effectiveSlippageBps() {
        return slippageBps == null ? DEFAULT_SLIPPAGE_BPS : slippageBps;
    }

    /** 有效手续费基点（0 或负值时使用默认值）。 */
    public double effectiveCommissionBps() {
        return commissionBps > 0 ? commissionBps : DEFAULT_COMMISSION_BPS;
    }

    /** 有效调仓间隔（0 或负值时使用默认值）。 */
    public int effectiveRebalanceInterval() {
        return rebalanceInterval > 0 ? rebalanceInterval : DEFAULT_REBALANCE_INTERVAL;
    }

    /** 有效持有期（0 或负值时使用默认值）。 */
    public int effectiveHoldingPeriod() {
        return holdingPeriod > 0 ? holdingPeriod : DEFAULT_HOLDING_PERIOD;
    }

    /** 有效最大持仓数（0 或负值时使用默认值）。 */
    public int effectiveMaxPositions() {
        return maxPositions > 0 ? maxPositions : DEFAULT_MAX_POSITIONS;
    }

    /** 有效执行延迟天数（永不为 null）。 */
    public int effectiveExecutionDelay() {
        return executionDelay == null ? DEFAULT_EXECUTION_DELAY : executionDelay;
    }

    /** 有效基准指数代码（永不为 null）。 */
    public String effectiveBenchmarkCode() {
        return benchmarkCode == null ? DEFAULT_BENCHMARK_CODE : benchmarkCode;
    }

    /** 有效单笔成交量限制百分比（null 表示不限制）。 */
    public Double effectiveMaxVolumePct() {
        return maxVolumePct;
    }

    /** 有效止损百分比（null 時使用默認 10%）。 */
    public Double effectiveStopLossPct() {
        return stopLossPct != null ? stopLossPct : DEFAULT_STOP_LOSS_PCT;
    }
}
