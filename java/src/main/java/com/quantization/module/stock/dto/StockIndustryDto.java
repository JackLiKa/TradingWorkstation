package com.quantization.module.stock.dto;

import java.time.LocalDate;

/**
 * 股票行業分類 DTO。
 */
public record StockIndustryDto(
        Long id,
        String code,
        LocalDate updateDate,
        String codeName,
        String industry,
        String industryClassification
) {
    public static StockIndustryDto from(com.quantization.module.stock.StockIndustryEntity e) {
        return new StockIndustryDto(
                e.getId(),
                e.getCode(),
                e.getUpdateDate(),
                e.getCodeName(),
                e.getIndustry(),
                e.getIndustryClassification()
        );
    }
}
