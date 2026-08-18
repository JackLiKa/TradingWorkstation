package com.quantization.module.backtest.dto;

import com.quantization.module.screener.dto.ScreenerCriteriaDto;

/**
 * 保存回測策略請求。
 * result 為可選 — 若提供則一併保存回測結果。
 */
public record SaveStrategyDto(
        String name,
        ScreenerCriteriaDto criteria,
        BacktestConfigDto config,
        BacktestResultDto result
) {
}
