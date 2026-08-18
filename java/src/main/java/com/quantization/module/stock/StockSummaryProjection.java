package com.quantization.module.stock;

import java.math.BigDecimal;
import java.time.LocalDate;

/** 汇总指标投影（构造表达式用）。 */
public record StockSummaryProjection(
        long totalRecords,
        long totalSymbols,
        LocalDate latestTradeDate,
        Double averagePctChange,
        Double latestTurnover
) {
    public StockSummaryProjection(
            Long totalRecords,
            Long totalSymbols,
            LocalDate latestTradeDate,
            BigDecimal averagePctChange,
            BigDecimal latestTurnover
    ) {
        this(
                totalRecords == null ? 0L : totalRecords,
                totalSymbols == null ? 0L : totalSymbols,
                latestTradeDate,
                averagePctChange == null ? null : averagePctChange.doubleValue(),
                latestTurnover == null ? null : latestTurnover.doubleValue()
        );
    }
}
