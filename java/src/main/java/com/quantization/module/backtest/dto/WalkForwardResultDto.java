package com.quantization.module.backtest.dto;

import java.util.List;

/**
 * Walk-forward 回測結果 DTO。
 *
 * @param trainResult 訓練段回測結果（樣本內）
 * @param testResult  測試段回測結果（樣本外）
 * @param overfitScore 過擬合評分（train Sharpe / test Sharpe，>2 表示嚴重過擬合）
 * @param summary     摘要文字
 */
public record WalkForwardResultDto(
        BacktestResultDto trainResult,
        BacktestResultDto testResult,
        double overfitScore,
        String summary
) {}
