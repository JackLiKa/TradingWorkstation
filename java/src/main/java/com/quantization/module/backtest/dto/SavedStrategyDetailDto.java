package com.quantization.module.backtest.dto;

import com.quantization.module.screener.dto.ScreenerCriteriaDto;

import java.time.LocalDateTime;

/**
 * 已保存策略詳情（含配置和可選的完整結果）。
 */
public record SavedStrategyDetailDto(
        Long id,
        String name,
        ScreenerCriteriaDto criteria,
        BacktestConfigDto config,
        BacktestResultDto result,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
