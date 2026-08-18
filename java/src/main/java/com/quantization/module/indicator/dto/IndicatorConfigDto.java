package com.quantization.module.indicator.dto;

import java.util.List;

/**
 * 技术指标配置 DTO（前端传入），控制各指标的显示和参数。
 * 字段均为包装类型，null 表示使用默认值。
 */
public record IndicatorConfigDto(
        Boolean showMa,
        List<Integer> maPeriods,
        Boolean showBoll,
        Boolean showMacd,
        Boolean showKdj,
        Integer bollPeriod,
        Double bollStd,
        Integer macdFastPeriod,
        Integer macdSlowPeriod,
        Integer macdSignalPeriod,
        Integer kdjPeriod,
        Integer kdjKSmoothing,
        Integer kdjDSmoothing
) {
}
