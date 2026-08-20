package com.quantization.module.stock.dto;

import java.time.LocalDate;

/**
 * 板塊單日表現 DTO — 某交易日某行業的平均漲跌幅和領漲股。
 */
public record SectorPerformanceDto(
        LocalDate date,
        String industry,
        Double avgPctChange,
        String topCode,
        String topCodeName,
        Double topPctChange
) {
}
