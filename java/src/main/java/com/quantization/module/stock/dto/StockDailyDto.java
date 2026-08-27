package com.quantization.module.stock.dto;

import java.time.LocalDate;

/**
 * 股票日线 DTO，对应 stock_daily 表的行数据，用于 API 响应。
 */
public record StockDailyDto(
        String code,
        LocalDate tradeDate,
        Double open,
        Double high,
        Double low,
        Double close,
        Double preclose,
        Long volume,
        Double amount,
        int adjustflag,
        Double turn,
        Integer tradeStatus,
        Double pctChange,
        Integer isSt
) {
}
