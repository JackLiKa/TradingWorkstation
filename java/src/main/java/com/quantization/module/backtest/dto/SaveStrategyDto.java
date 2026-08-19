package com.quantization.module.backtest.dto;

import com.quantization.module.screener.dto.ScreenerCriteriaDto;

/**
 * 保存回測策略請求。
 * result 為可選 — 若提供則一併保存回測結果。
 * source 為可選 — manual=手動保存（默認），auto=回測自動保存。
 */
public record SaveStrategyDto(
        String name,
        ScreenerCriteriaDto criteria,
        BacktestConfigDto config,
        BacktestResultDto result,
        String source
) {
    /** 向後兼容：source 默認為 manual */
    public String effectiveSource() {
        return (source == null || source.isBlank()) ? "manual" : source;
    }
}
