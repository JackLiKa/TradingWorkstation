package com.quantization.module.stock.dto;

import java.util.List;

/**
 * 輪動預測 AutoML 自動調參結果 DTO。
 *
 * 自動嘗試多組 lookbackDays × forwardDays 組合，
 * 基於回測命中率和超額收益找出最佳參數組合。
 */
public record RotationAutoMlDto(
        int bestLookbackDays,
        int bestForwardDays,
        double bestHitRate,
        double bestExcessReturn,
        double bestCompositeScore,
        String summary,
        List<ParamCombination> combinations
) {
    /**
     * 單組參數組合的回測結果。
     *
     * @param lookbackDays     回溯天數
     * @param forwardDays      前瞻天數
     * @param hitRate          命中率（%）
     * @param avgExcessReturn  平均超額收益（%）
     * @param avgLeaderReturn  預測領漲平均收益（%）
     * @param totalPredictions 回測次數
     * @param compositeScore   綜合評分（命中率 * 0.6 + 超額收益標準化 * 0.4）
     */
    public record ParamCombination(
            int lookbackDays,
            int forwardDays,
            double hitRate,
            double avgExcessReturn,
            double avgLeaderReturn,
            int totalPredictions,
            double compositeScore,
            double evalHitRate,
            double evalExcessReturn
    ) {
    }
}
