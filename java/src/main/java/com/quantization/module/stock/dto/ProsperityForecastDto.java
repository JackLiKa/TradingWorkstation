package com.quantization.module.stock.dto;

import java.util.List;
import java.util.Map;

/**
 * 行業景氣度多模型預測 DTO — 整合 ARIMA、Holt-Winters、線性回歸三個模型。
 *
 * 三個模型均為輕量級 CPU 模型（純 Java 實作，無額外依賴）：
 * 1. ARIMA：簡化版 AR(2) + 一階差分，捕捉自相關性
 * 2. Holt-Winters：三重指數平滑，捕捉趨勢 + 季節性
 * 3. 線性回歸：OLS 趨勢預測，捕捉線性趨勢
 *
 * 最終預測 = 三個模型的加權平均。權重來源由 {@link #weightSource} 標識：
 * {@code "fixed"} = 固定權重 0.35/0.35/0.30；{@code "adaptive"} = 滾動窗口逆 MAE 動態權重。
 *
 * @param analysisDate 分析基準日
 * @param forecastDays 預測天數
 * @param industries   各行業預測結果
 * @param summary      摘要文字
 * @param weightSource 權重來源（"fixed" 或 "adaptive"）
 */
public record ProsperityForecastDto(
        String analysisDate,
        int forecastDays,
        Map<String, IndustryForecast> industries,
        String summary,
        String weightSource
) {
    /**
     * 單個行業的多模型預測結果。
     *
     * @param industry         行業名稱
     * @param arimaForecast    ARIMA 模型預測值列表（未來 N 日）
     * @param holtWintersForecast Holt-Winters 模型預測值列表
     * @param linearForecast   線性回歸預測值列表
     * @param ensembleForecast 整合預測值列表（加權平均）
     * @param currentProsperity 當前景氣度
     * @param arimaTrend       ARIMA 趨勢（上升/下降/平穩）
     * @param holtWintersTrend Holt-Winters 趨勢
     * @param linearTrend      線性回歸趨勢
     * @param consensusTrend   共識趨勢（三模型多數決）
     * @param forecastDates    預測日期列表
     * @param arimaWeight      整合時 ARIMA 實際使用權重
     * @param holtWintersWeight 整合時 Holt-Winters 實際使用權重
     * @param linearWeight     整合時線性回歸實際使用權重
     */
    public record IndustryForecast(
            String industry,
            List<Double> arimaForecast,
            List<Double> holtWintersForecast,
            List<Double> linearForecast,
            List<Double> ensembleForecast,
            double currentProsperity,
            String arimaTrend,
            String holtWintersTrend,
            String linearTrend,
            String consensusTrend,
            List<String> forecastDates,
            double arimaWeight,
            double holtWintersWeight,
            double linearWeight
    ) {
    }
}
