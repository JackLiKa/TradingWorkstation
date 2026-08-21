package com.quantization.module.stock.dto;

import java.time.LocalDate;

/**
 * 行業景氣度指標 DTO — 基於漲跌幅、成交額、換手率綜合評分。
 *
 * 評分維度：
 * - momentumScore: 漲跌幅標準化分數（0-100）
 * - capitalScore: 成交額標準化分數（0-100）
 * - activityScore: 換手率標準化分數（0-100）
 * - breadthScore: 上漲家數佔比標準化分數（0-100）
 * - prosperityIndex: 綜合景氣度指數（加權平均，0-100）
 */
public record IndustryProsperityDto(
        LocalDate tradeDate,
        String industry,
        Double avgPctChg,
        Double totalAmount,
        Double avgTurn,
        Integer risingCount,
        Integer fallingCount,
        Double momentumScore,
        Double capitalScore,
        Double activityScore,
        Double breadthScore,
        Double prosperityIndex,
        String grade
) {
}
