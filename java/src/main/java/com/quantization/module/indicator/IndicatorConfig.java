package com.quantization.module.indicator;

import java.util.List;

/**
 * 指标计算配置（与原 IndicatorConfig 对齐）。
 */
public record IndicatorConfig(
        boolean showMa,
        List<Integer> maPeriods,
        boolean showBoll,
        boolean showMacd,
        boolean showKdj,
        int bollPeriod,
        double bollStd,
        int macdFastPeriod,
        int macdSlowPeriod,
        int macdSignalPeriod,
        int kdjPeriod,
        int kdjKSmoothing,
        int kdjDSmoothing
) {
    public static IndicatorConfig defaults() {
        return new IndicatorConfig(
                true, List.of(5, 10, 20),
                false, false, false,
                20, 2.0,
                12, 26, 9,
                9, 3, 3
        );
    }

    public static IndicatorConfig screener() {
        return new IndicatorConfig(
                true, List.of(5, 10, 20, 60, 120),
                true, true, true,
                20, 2.0,
                12, 26, 9,
                9, 3, 3
        );
    }
}
