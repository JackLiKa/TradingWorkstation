package com.quantization.module.indicator;

import java.util.List;
import java.util.Map;

/**
 * 指标全序列（供 K 线图叠加副图使用），与输入 records 等长、按时间升序对齐。
 * 每个元素可为 null（数据不足时）。
 */
public record IndicatorSeries(
        Map<Integer, List<Double>> maSeries,
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
}
