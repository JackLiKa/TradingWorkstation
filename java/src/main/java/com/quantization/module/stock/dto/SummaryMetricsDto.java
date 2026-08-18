package com.quantization.module.stock.dto;

import java.time.LocalDate;

/**
 * 汇总指标 DTO，包含总记录数、去重股票数、最新交易日及当日平均涨跌幅与成交额。
 */
public record SummaryMetricsDto(
        long totalRecords,
        long totalSymbols,
        LocalDate latestTradeDate,
        Double averagePctChange,
        Double latestTurnover
) {
}
