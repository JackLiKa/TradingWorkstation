package com.quantization.module.screener.dto;

import com.quantization.module.indicator.IndicatorSnapshot;

import java.time.LocalDate;

/**
 * 选股命中股票 DTO，包含行情数据和全部技术指标快照。
 * 字段与 {@link com.quantization.module.indicator.IndicatorSnapshot} 一一对应。
 */
public record ScreenedStockDto(
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
    /**
     * 从指标快照 {@link com.quantization.module.indicator.IndicatorSnapshot} 转换为选股 DTO。
     *
     * @param s 指标快照
     * @return 选股命中股票 DTO
     */
    public static ScreenedStockDto from(IndicatorSnapshot s) {
        return new ScreenedStockDto(
                s.code(), s.tradeDate(), s.closePrice(), s.pctChange(), s.amplitude(), s.turn(),
                s.volume(), s.amount(), s.ma5(), s.ma10(), s.ma20(), s.ma60(), s.ma120(),
                s.volumeRatio(), s.return20(), s.return60(), s.return120(), s.rsi14(),
                s.kValue(), s.dValue(), s.jValue(), s.kdjCrossSignal(), s.kdjGoldenCrossDaysAgo(), s.kdjDeathCrossDaysAgo(),
                s.dif(), s.dea(), s.macdHist(), s.macdCrossSignal(), s.macdGoldenCrossDaysAgo(), s.macdDeathCrossDaysAgo(),
                s.bollUpper(), s.bollMiddle(), s.bollLower(), s.bollWidth(), s.bollPercentB(), s.bollPosition(),
                s.score(), s.isSt());
    }
}
