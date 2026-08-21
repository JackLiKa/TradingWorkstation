package com.quantization.module.stock.dto;

import java.util.List;
import java.util.Map;

/**
 * 行業景氣度週期性分析 DTO — 檢測季節性模式與週期規律。
 *
 * 分析維度：
 * 1. 月度模式：各行業在每個月的平均景氣度（1-12月）
 * 2. 星期模式：各行業在每個星期的平均景氣度（週一至週五）
 * 3. 季節性強度：各行業景氣度的季節性變異佔比（季節性方差 / 總方差）
 * 4. 最佳/最差月份：各行業景氣度最高和最低的月份
 */
public record ProsperitySeasonalityDto(
        String analysisPeriod,
        int totalDataPoints,
        Map<String, MonthlyPattern> industries,
        String summary
) {
    /**
     * 單個行業的週期性模式。
     *
     * @param industry          行業名稱
     * @param monthlyAvg        月度平均景氣度（key=月份1-12, value=平均景氣度）
     * @param weekdayAvg        星期平均景氣度（key=星期1-5, value=平均景氣度）
     * @param bestMonth         景氣度最高的月份
     * @param worstMonth        景氣度最低的月份
     * @param bestMonthAvg      最高月份的平均景氣度
     * @param worstMonthAvg     最低月份的平均景氣度
     * @param seasonalityStrength 季節性強度（0-1，越高表示季節性越明顯）
     * @param overallAvg        整體平均景氣度
     */
    public record MonthlyPattern(
            String industry,
            Map<Integer, Double> monthlyAvg,
            Map<Integer, Double> weekdayAvg,
            int bestMonth,
            int worstMonth,
            double bestMonthAvg,
            double worstMonthAvg,
            double seasonalityStrength,
            double overallAvg
    ) {
    }
}
