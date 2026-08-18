package com.quantization.module.stock.dto;

/**
 * 波动榜 DTO，包含股票代码、收盘价、涨跌幅和成交量。
 */
public record HotSymbolDto(
        String code,
        Double closePrice,
        Double pctChange,
        Long volume
) {
}
