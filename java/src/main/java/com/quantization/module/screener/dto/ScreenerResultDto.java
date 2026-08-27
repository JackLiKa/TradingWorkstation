package com.quantization.module.screener.dto;

import java.time.LocalDate;
import java.util.List;

/**
 * 选股结果 DTO，包含筛选条件、基准日期、扫描统计和命中股票列表。
 *
 * @param criteria        选股条件
 * @param screenDate      实际筛选基准日（可能因非交易日自动回退）
 * @param scannedSymbols  扫描股票总数
 * @param matchedSymbols  命中股票数
 * @param candidates      命中股票列表（按指定字段排序）
 * @param summaryLines    摘要日志行
 */
public record ScreenerResultDto(
        ScreenerCriteriaDto criteria,
        LocalDate screenDate,
        int scannedSymbols,
        int matchedSymbols,
        List<ScreenedStockDto> candidates,
        List<String> summaryLines
) {
}
