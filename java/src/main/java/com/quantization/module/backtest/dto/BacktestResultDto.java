package com.quantization.module.backtest.dto;

import java.time.LocalDate;
import java.util.List;

/**
 * 回测结果 DTO，包含净值曲线、调仓事件和统计指标。
 *
 * @param config         回测配置
 * @param strategyCurve  策略净值曲线
 * @param benchmarkCurve 基准净值曲线
 * @param excessCurve    超额收益曲线
 * @param rebalances     调仓事件列表
 * @param statistics     统计指标
 * @param logLines       日志摘要行
 */
public record BacktestResultDto(
        BacktestConfigDto config,
        List<EquityPoint> strategyCurve,
        List<EquityPoint> benchmarkCurve,
        List<EquityPoint> excessCurve,
        List<RebalanceEvent> rebalances,
        BacktestStatistics statistics,
        List<String> logLines
) {
    public record EquityPoint(LocalDate date, double value) {}
    public record RebalanceEvent(LocalDate date, List<String> bought, List<String> sold, List<String> held) {}
    public record BacktestStatistics(
            double totalReturn,
            double annualReturn,
            double benchmarkReturn,
            double excessReturn,
            double maxDrawdown,
            double sharpe,
            int rebalanceCount,
            int totalTrades
    ) {}
}
