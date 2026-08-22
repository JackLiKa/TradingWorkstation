package com.quantization.module.stock.dto;

import java.util.List;

/**
 * 行業景氣度預測回測 DTO — 驗證多模型預測的歷史準確率。
 *
 * 回測邏輯：
 * 1. 對每個歷史交易日 T，用 T 之前的數據預測 T+forecastDays 的景氣度
 * 2. 比較預測值與實際景氣度
 * 3. 計算 MAE（平均絕對誤差）、方向準確率、等級命中率和超額收益
 *
 * 評估指標：
 * - MAE：預測值與實際值的平均絕對誤差（越小越好）
 * - 方向準確率：預測上升/下降方向正確的比例
 * - 等級命中率：預測等級與實際等級一致的比例
 * - 超額收益：基於預測做多 Top N 行業的收益 vs 市場平均
 */
public record ProsperityForecastBacktestDto(
        int forecastDays,
        int totalPredictions,
        double mae,
        double directionAccuracy,
        double gradeHitRate,
        double avgTopReturn,
        double avgMarketReturn,
        double avgExcessReturn,
        String summary,
        List<BacktestEntry> entries,
        double arimaMae,
        double hwMae,
        double linearMae,
        String optimalWeights
) {
    /**
     * 單次回測記錄。
     *
     * @param predictDate       預測日期 T
     * @param targetDate        目標日期 T+forecastDays
     * @param topPredicted      預測景氣度最高的行業
     * @param topActual         實際景氣度最高的行業
     * @param predictedProsperity 預測景氣度
     * @param actualProsperity  實際景氣度
     * @param absError          絕對誤差
     * @param directionCorrect  方向預測是否正確
     * @param gradeCorrect      等級預測是否正確
     */
    public record BacktestEntry(
            String predictDate,
            String targetDate,
            String topPredicted,
            String topActual,
            double predictedProsperity,
            double actualProsperity,
            double absError,
            boolean directionCorrect,
            boolean gradeCorrect
    ) {
    }
}
