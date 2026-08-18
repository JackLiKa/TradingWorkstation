package com.quantization.module.indicator;

import java.time.LocalDate;
import java.util.List;

/**
 * 单只股票在某一交易日的指标快照（供选股器筛选与评分使用）。
 * 字段与原 Python ScreenedStock 对齐。
 */
public record IndicatorSnapshot(
        String code,
        LocalDate tradeDate,
        double closePrice,
        double pctChange,
        double amplitude,
        double turn,
        long volume,
        double amount,
        Double ma5,
        Double ma10,
        Double ma20,
        Double ma60,
        Double ma120,
        Double volumeRatio,
        Double return20,
        Double return60,
        Double return120,
        Double rsi14,
        Double kValue,
        Double dValue,
        Double jValue,
        String kdjCrossSignal,
        Integer kdjGoldenCrossDaysAgo,
        Integer kdjDeathCrossDaysAgo,
        Double dif,
        Double dea,
        Double macdHist,
        String macdCrossSignal,
        Integer macdGoldenCrossDaysAgo,
        Integer macdDeathCrossDaysAgo,
        Double bollUpper,
        Double bollMiddle,
        Double bollLower,
        Double bollWidth,
        Double bollPercentB,
        String bollPosition,
        double score,
        boolean isSt
) {
}
