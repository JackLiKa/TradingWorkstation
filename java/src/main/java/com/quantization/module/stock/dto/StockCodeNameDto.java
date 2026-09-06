package com.quantization.module.stock.dto;

/**
 * 股票代碼+名稱輕量 DTO — 投影查詢專用。
 * <p>
 * 只包含 code 和 name 兩個字段，每條約 30 字節。
 * 用於行業股票列表查詢，避免加載完整實體導致內存問題。
 * </p>
 */
public record StockCodeNameDto(
        String code,
        String name
) {}
