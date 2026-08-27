package com.quantization.module.stock.dto;

import java.util.List;

/**
 * 行業景氣度異常預警 DTO — 檢測景氣度突變與等級躍遷。
 *
 * 預警類型：
 * 1. surge（景氣度突升）：今日景氣度 - 昨日景氣度 ≥ threshold
 * 2. plunge（景氣度突降）：昨日景氣度 - 今日景氣度 ≥ threshold
 * 3. grade_up（等級躍升）：等級從低到高（如 低迷 → 景氣）
 * 4. grade_down（等級躍降）：等級從高到低（如 繁榮 → 平穩）
 */
public record ProsperityAlertDto(
        String analysisDate,
        List<AlertEntry> alerts,
        String summary
) {
    /**
     * 單條預警。
     *
     * @param industry             行業名稱
     * @param alertType            預警類型（surge/plunge/grade_up/grade_down）
     * @param alertTypeName        預警類型中文名
     * @param yesterdayProsperity  昨日景氣度
     * @param todayProsperity      今日景氣度
     * @param change               變化值
     * @param yesterdayGrade       昨日等級
     * @param todayGrade           今日等級
     * @param severity             嚴重程度（high/medium/low）
     * @param message              預警訊息
     */
    public record AlertEntry(
            String industry,
            String alertType,
            String alertTypeName,
            double yesterdayProsperity,
            double todayProsperity,
            double change,
            String yesterdayGrade,
            String todayGrade,
            String severity,
            String message
    ) {
    }
}
