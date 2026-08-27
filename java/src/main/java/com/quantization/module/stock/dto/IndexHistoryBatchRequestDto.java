package com.quantization.module.stock.dto;

import java.util.List;

/**
 * 批量指數歷史查詢請求 DTO。
 */
public record IndexHistoryBatchRequestDto(
        List<String> codes,
        int days
) {
    public IndexHistoryBatchRequestDto {
        if (days <= 0) days = 10;
        if (days > 60) days = 60;
    }
}
