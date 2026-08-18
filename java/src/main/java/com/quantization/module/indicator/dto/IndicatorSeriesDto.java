package com.quantization.module.indicator.dto;

import com.quantization.module.indicator.IndicatorConfig;
import com.quantization.module.indicator.IndicatorSeries;

import java.util.List;
import java.util.Map;

/**
 * 技术指标序列 DTO（前端用），将 MA 周期 key 从 Integer 转为 String 以便 JSON 序列化。
 */
public record IndicatorSeriesDto(
        Map<String, List<Double>> maSeries,
        List<Double> bollUpper,
        List<Double> bollMiddle,
        List<Double> bollLower,
        List<Double> macdDif,
        List<Double> macdDea,
        List<Double> macdHist,
        List<Double> kdjK,
        List<Double> kdjD,
        List<Double> kdjJ,
        List<Double> rsi
) {
    /**
     * 从领域对象 {@link IndicatorSeries} 转换为 DTO，MA 周期 key 转为 String。
     *
     * @param s 指标序列领域对象
     * @return 指标序列 DTO
     */
    public static IndicatorSeriesDto from(IndicatorSeries s) {
        Map<String, List<Double>> ma = new java.util.HashMap<>();
        s.maSeries().forEach((k, v) -> ma.put(String.valueOf(k), v));
        return new IndicatorSeriesDto(ma, s.bollUpper(), s.bollMiddle(), s.bollLower(),
                s.macdDif(), s.macdDea(), s.macdHist(), s.kdjK(), s.kdjD(), s.kdjJ(), s.rsi());
    }
}
