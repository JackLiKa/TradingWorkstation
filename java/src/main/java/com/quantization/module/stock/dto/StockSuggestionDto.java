package com.quantization.module.stock.dto;

/**
 * 股票搜索建議：代碼 + 最新收盤價 + 漲跌幅，用於輸入框自動補全下拉。
 */
public record StockSuggestionDto(
        String code,
        Double closePrice,
        Double pctChange
) {
}
