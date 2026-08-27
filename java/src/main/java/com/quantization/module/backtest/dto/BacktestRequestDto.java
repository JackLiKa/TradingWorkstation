package com.quantization.module.backtest.dto;

import com.quantization.module.screener.dto.ScreenerCriteriaDto;

/**
 * 回测请求 DTO，包含选股条件和回测配置。
 *
 * @param criteria 选股条件
 * @param config   回测配置
 */
public record BacktestRequestDto(
        ScreenerCriteriaDto criteria,
        BacktestConfigDto config
) {
}
