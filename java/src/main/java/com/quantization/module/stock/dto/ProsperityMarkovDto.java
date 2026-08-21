package com.quantization.module.stock.dto;

import java.util.List;
import java.util.Map;

/**
 * 行業景氣度 Markov 狀態轉移模型 DTO。
 *
 * 將景氣度分為 5 個狀態（等級）：
 * 1=衰退, 2=低迷, 3=平穩, 4=景氣, 5=繁榮
 *
 * 基於歷史等級轉換構建一階 Markov 轉移矩陣，
 * 預測各行業下一日的等級轉換概率。
 */
public record ProsperityMarkovDto(
        String analysisDate,
        int totalTransitions,
        Map<String, IndustryMarkov> industries,
        String summary
) {
    /**
     * 單個行業的 Markov 分析結果。
     *
     * @param industry           行業名稱
     * @param transitionMatrix   5x5 轉移矩陣（transitionMatrix[from][to] = P(to|from)）
     * @param currentState       當前等級（1-5）
     * @param currentStateName   當前等級名稱
     * @param nextProbabilities  下一日各等級的概率（key=等級1-5, value=概率0-1）
     * @param steadyState        穩態分布（key=等級1-5, value=概率0-1）
     * @param transitionCount    該行業的歷史轉換次數
     * @param mostLikelyNext     最可能的下一等級名稱
     * @param mostLikelyNextProb 最可能下一等級的概率
     */
    public record IndustryMarkov(
            String industry,
            double[][] transitionMatrix,
            int currentState,
            String currentStateName,
            Map<Integer, Double> nextProbabilities,
            Map<Integer, Double> steadyState,
            int transitionCount,
            String mostLikelyNext,
            double mostLikelyNextProb
    ) {
    }
}
