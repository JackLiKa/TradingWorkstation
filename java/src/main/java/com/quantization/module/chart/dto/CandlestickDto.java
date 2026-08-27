package com.quantization.module.chart.dto;

import com.quantization.module.indicator.dto.IndicatorSeriesDto;
import com.quantization.module.stock.dto.StockDailyDto;

import java.util.List;

/**
 * K线数据 DTO，包含 OHLCV 记录列表、是否有更早历史标志和技术指标序列。
 *
 * @param code       股票代码
 * @param records    K线记录列表（按日期升序）
 * @param hasMore    是否还有更早的历史数据
 * @param indicators 技术指标序列（可为 null）
 */
public record CandlestickDto(
        String code,
        List<StockDailyDto> records,
        boolean hasMore,
        IndicatorSeriesDto indicators
) {
}
