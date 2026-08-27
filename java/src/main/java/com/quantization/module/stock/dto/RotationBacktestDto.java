package com.quantization.module.stock.dto;

import java.util.List;

/**
 * 行業輪動預測回測 DTO — 驗證歷史預測準確率。
 *
 * 回測邏輯：
 * 1. 對每個歷史交易日 T，用 T 之前 lookbackDays 的數據生成預測
 * 2. 檢查 T 之後 forwardDays 內，預測領漲行業是否實際領漲
 * 3. 計算命中率、平均超額收益等指標
 */
public record RotationBacktestDto(
        int lookbackDays,
        int forwardDays,
        int totalPredictions,
        int hitCount,
        double hitRate,
        double avgLeaderReturn,
        double avgLaggardReturn,
        double avgExcessReturn,
        String summary,
        List<BacktestEntry> entries
) {
    /**
     * 單次回測記錄。
     *
     * @param predictDate     預測日期 T
     * @param topPredicted    預測領漲行業（Top 1）
     * @param actualTopIndustry 實際領漲行業（T+forwardDays 內累計漲幅最高）
     * @param predictedReturn 預測領漲行業的實際收益
     * @param marketAvgReturn 市場平均收益
     * @param excessReturn    超額收益
     * @param hit             是否命中（預測領漲在實際 Top 5 內）
     */
    public record BacktestEntry(
            String predictDate,
            String topPredicted,
            String actualTopIndustry,
            double predictedReturn,
            double marketAvgReturn,
            double excessReturn,
            boolean hit
    ) {
    }
}
