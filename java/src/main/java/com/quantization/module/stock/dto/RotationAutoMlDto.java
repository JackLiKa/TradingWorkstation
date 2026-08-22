package com.quantization.module.stock.dto;

import java.util.List;

/**
 * 輪動預測 AutoML 自動調參結果 DTO。
 *
 * 自動嘗試多組 lookbackDays × forwardDays 組合，
 * 基於回測命中率和超額收益找出最佳參數組合。
 *
 * 採用嚴格日期隔離 out-of-sample 評估設計：
 * - 調參（tune）只用區間 A 的數據做網格搜索
 * - 評估（eval）只用區間 B 的數據（B 在 A 之後，完全不重疊）
 * - 最終報告在區間 B 上的表現
 *
 * @param tuneRange 調參區間 A 的日期範圍描述（如 "2025-01-01 ~ 2025-06-30"）
 * @param evalRange 評估區間 B 的日期範圍描述（如 "2025-07-01 ~ 2025-09-30"）
 */
public record RotationAutoMlDto(
        int bestLookbackDays,
        int bestForwardDays,
        double bestHitRate,
        double bestExcessReturn,
        double bestCompositeScore,
        String summary,
        List<ParamCombination> combinations,
        String tuneRange,
        String evalRange
) {
    /**
     * 單組參數組合的回測結果。
     *
     * @param lookbackDays     回溯天數
     * @param forwardDays      前瞻天數
     * @param hitRate          調參段命中率（%）
     * @param avgExcessReturn  調參段平均超額收益（%）
     * @param avgLeaderReturn  調參段預測領漲平均收益（%）
     * @param totalPredictions 調參段回測次數
     * @param compositeScore   綜合評分（命中率 * 0.6 + 超額收益標準化 * 0.4）
     * @param evalHitRate      評估段命中率（%，僅最佳組合在區間 B 上有值，其餘為 0）
     * @param evalExcessReturn 評估段平均超額收益（%，僅最佳組合在區間 B 上有值，其餘為 0）
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
