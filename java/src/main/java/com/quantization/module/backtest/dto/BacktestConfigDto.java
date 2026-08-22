package com.quantization.module.backtest.dto;

import java.time.LocalDate;

/**
 * 回测配置 DTO，定义回测的时间范围、调仓参数、资金和手续费等。
 *
 * @param startDate        回测起始日期
 * @param endDate          回测结束日期
 * @param rebalanceInterval 调仓间隔（交易日数）
 * @param holdingPeriod     持有期（交易日数）
 * @param maxPositions      最大持仓数
 * @param initialCapital    初始资金
 * @param commissionBps     手续费（基点，1bp = 0.01%）
 * @param stopLossPct       止损百分比（null 表示不启用）
 * @param takeProfitPct     止盈百分比（null 表示不启用）
 * @param riskFreeRate      无风险年化利率（默认 0.02），用于夏普比率计算
 * @param slippageBps       滑点（基点，默认 0），买入价上浮、卖出价下浮
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
        Integer slippageBps
) {
    /** 默认无风险年化利率。 */
    public static final double DEFAULT_RISK_FREE_RATE = 0.02;
    /** 默认滑点（基点）。 */
    public static final int DEFAULT_SLIPPAGE_BPS = 0;

    public BacktestConfigDto {
        if (riskFreeRate == null) riskFreeRate = DEFAULT_RISK_FREE_RATE;
        if (slippageBps == null) slippageBps = DEFAULT_SLIPPAGE_BPS;
    }

    /** 有效无风险年化利率（永不为 null）。 */
    public double effectiveRiskFreeRate() {
        return riskFreeRate == null ? DEFAULT_RISK_FREE_RATE : riskFreeRate;
    }

    /** 有效滑点基点（永不为 null）。 */
    public int effectiveSlippageBps() {
        return slippageBps == null ? DEFAULT_SLIPPAGE_BPS : slippageBps;
    }
}
