package com.quantization.module.stock.dto;

import com.quantization.module.stock.IndexDailyEntity;

import java.time.LocalDate;

/**
 * 指数日线 DTO，包含指数代码、交易日期、收盘价和涨跌幅。
 * 用于多日指数历史查询，支持市场形态识别。
 */
public record IndexDailyDto(
        String code,
        LocalDate tradeDate,
        Double closePrice,
        Double pctChange
) {
    public static IndexDailyDto from(IndexDailyEntity entity) {
        return new IndexDailyDto(
                entity.getCode(),
                entity.getTradeDate(),
                entity.getClosePrice() != null ? entity.getClosePrice().doubleValue() : null,
                entity.getPctChange() != null ? entity.getPctChange().doubleValue() : null
        );
    }
}
