package com.quantization.module.backtest.dto;

import java.time.LocalDateTime;

/**
 * 已保存策略摘要（列表用，不含完整結果數據）。
 */
public record SavedStrategySummaryDto(
        Long id,
        String name,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
