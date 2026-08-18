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
        Double takeProfitPct
) {
}
