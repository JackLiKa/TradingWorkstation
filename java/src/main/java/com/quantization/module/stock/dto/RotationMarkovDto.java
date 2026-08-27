package com.quantization.module.stock.dto;

import java.util.List;
import java.util.Map;

/**
 * 行業輪動 Markov 模型 DTO — 預測領漲行業轉換概率。
 *
 * 將行業按每日漲跌幅排名分為 3 個狀態：
 * 1=領漲（Top 1/3）、2=中間（Middle 1/3）、3=滯後（Bottom 1/3）
 *
 * 基於歷史狀態轉換構建一階 Markov 轉移矩陣，
 * 預測各行業下一期從當前狀態轉移到其他狀態的概率。
 */
public record RotationMarkovDto(
        String analysisDate,
        int totalTransitions,
        Map<String, IndustryRotationMarkov> industries,
        String summary
) {
    /**
     * 單個行業的輪動 Markov 分析結果。
     *
     * @param industry           行業名稱
     * @param transitionMatrix   3x3 轉移矩陣（transitionMatrix[from][to] = P(to|from)）
     * @param currentState       當前狀態（1=領漲, 2=中間, 3=滯後）
     * @param currentStateName   當前狀態名稱
     * @param nextProbabilities  下一期各狀態的概率（key=狀態1-3, value=概率0-1）
     * @param steadyState        穩態分布（key=狀態1-3, value=概率0-1）
     * @param transitionCount    該行業的歷史轉換次數
     * @param mostLikelyNext     最可能的下一狀態名稱
     * @param mostLikelyNextProb 最可能下一狀態的概率
     * @param leaderProbability  成為領漲的長期概率（穩態分布中狀態1的概率）
     */
    public record IndustryRotationMarkov(
            String industry,
            double[][] transitionMatrix,
            int currentState,
            String currentStateName,
            Map<Integer, Double> nextProbabilities,
            Map<Integer, Double> steadyState,
            int transitionCount,
            String mostLikelyNext,
            double mostLikelyNextProb,
            double leaderProbability
    ) {
    }
}
