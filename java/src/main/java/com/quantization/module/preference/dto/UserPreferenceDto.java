package com.quantization.module.preference.dto;

import java.util.List;
import java.util.Map;

/**
 * 用户偏好 DTO，包含默认查询参数、自选股、选股预设和指标配置等。
 */
public record UserPreferenceDto(
        String defaultAdjustflag,
        Integer defaultLimit,
        Integer defaultLookbackDays,
        List<String> watchlist,
        Map<String, ScreenerPresetDto> screenerPresets,
        IndicatorConfigPreferenceDto indicatorConfig,
        String defaultSortBy
) {
    /**
     * 构建默认空偏好。
     *
     * @return 默认偏好（不复权、200条、180天回看、空自选股、默认指标配置）
     */
    public static UserPreferenceDto empty() {
        return new UserPreferenceDto("3", 200, 180, List.of(), Map.of(), IndicatorConfigPreferenceDto.defaults(), "score");
    }

    public record ScreenerPresetDto(String name, String description, Map<String, Object> criteria) {}

    public record IndicatorConfigPreferenceDto(
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
        public static IndicatorConfigPreferenceDto defaults() {
            return new IndicatorConfigPreferenceDto(true, List.of(5, 10, 20), false, false, false,
                    20, 2.0, 12, 26, 9, 9, 3, 3);
        }
    }
}
