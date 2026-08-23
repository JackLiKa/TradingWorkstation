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
            int totalTrades,
            // 風控指標（Phase C4 新增）
            double sortino,           // Sortino Ratio（只懲罰下行波動）
            double calmar,            // Calmar Ratio（年化收益/最大回撤）
            double informationRatio,  // Information Ratio（超額收益/跟蹤誤差）
            double beta,              // Beta（策略 vs 基準系統性風險）
            double alpha,             // Alpha（Jensen's Alpha，超額收益的系統性部分）
            double winRate,           // 勝率（盈利交易日佔比）
            double profitLossRatio,   // 盈虧比（平均盈利/平均虧損）
            double annualTurnover,    // 年化換手率
            double deflatedSharpe,    // Deflated Sharpe Ratio（多重檢驗修正）
            int nTrials,              // 試驗次數（用於 Deflated Sharpe 計算）
            double pbo                // Probability of Backtest Overfitting
    ) {
        /** 向後兼容：舊的 8 參數構造（新指標填 0）。 */
        public BacktestStatistics(double totalReturn, double annualReturn, double benchmarkReturn,
                                  double excessReturn, double maxDrawdown, double sharpe,
                                  int rebalanceCount, int totalTrades) {
            this(totalReturn, annualReturn, benchmarkReturn, excessReturn, maxDrawdown, sharpe,
                 rebalanceCount, totalTrades, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
        }
    }
}
