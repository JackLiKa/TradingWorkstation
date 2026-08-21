package com.quantization.module.stock.dto;

import com.quantization.module.stock.IndustryDailyEntity;

import java.time.LocalDate;

/**
 * 行業日度聚合 DTO，用於行業熱力圖、行情分析等場景。
 */
public record IndustryDailyDto(
        LocalDate tradeDate,
        String industry,
        Integer stockCount,
        Double avgPctChg,
        Double totalAmount,
        Long totalVolume,
        Double avgTurn,
        Integer risingCount,
        Integer fallingCount,
        Double avgClose,
        Double maxClose,
        Double minClose
) {
    public static IndustryDailyDto from(IndustryDailyEntity entity) {
        return new IndustryDailyDto(
                entity.getTradeDate(),
                entity.getIndustry(),
                entity.getStockCount(),
                toDouble(entity.getAvgPctChg()),
                toDouble(entity.getTotalAmount()),
                entity.getTotalVolume(),
                toDouble(entity.getAvgTurn()),
                entity.getRisingCount(),
                entity.getFallingCount(),
                toDouble(entity.getAvgClose()),
                toDouble(entity.getMaxClose()),
                toDouble(entity.getMinClose())
        );
    }

    private static Double toDouble(Number value) {
        return value == null ? null : value.doubleValue();
    }
}
