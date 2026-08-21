package com.quantization.module.stock.dto;

import java.util.List;

/**
 * 行業輪動預測 DTO — 基於歷史輪動規律預測下一輪領漲行業。
 *
 * 預測模型：
 * 1. 動量延續：近期強勢行業可能繼續領漲（慣性效應）
 * 2. 輪動接力：歷史上滯後行業在領漲行業回調後可能接力
 * 3. 資金流向：資金持續流入的行業更可能成為下一輪領漲
 * 4. 景氣度趨勢：景氣度上升的行業有更大機會成為領漲
 */
public record RotationPredictionDto(
        String analysisDate,
        String predictionWindow,
        List<PredictedIndustry> predictedLeaders,
        List<PredictedIndustry> predictedLaggards,
        String predictionReasoning,
        double confidence
) {
    /**
     * 預測行業項。
     *
     * @param industry      行業名稱
     * @param score         綜合預測評分（0-100，越高越可能領漲）
     * @param momentumScore 動量評分（近期漲跌幅標準化）
     * @param capitalScore  資金評分（成交額變化標準化）
     * @param trendScore    趨勢評分（景氣度變化標準化）
     * @param reason        預測理由
     */
    public record PredictedIndustry(
            String industry,
            double score,
            double momentumScore,
            double capitalScore,
            double trendScore,
            String reason
    ) {
    }
}
