package com.quantization.module.indicator;

import com.quantization.module.stock.StockDaily;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 指标引擎：基于 {@link IndicatorMath} 组合，提供候选快照与全序列计算。
 * 高内聚：所有技术指标计算集中于此模块，供 dashboard/screener/backtest/chart 复用。
 */
@Service
public class IndicatorEngine {

    /**
     * 构建单只股票在最新交易日的指标快照（与原 Python _build_candidate 对齐）。
     * 返回 null 表示数据不足或不可交易。
     */
    public IndicatorSnapshot buildSnapshot(String code, List<StockDaily> history, IndicatorConfig config) {
        if (history == null || history.size() < 30) return null;
        StockDaily latest = history.get(history.size() - 1);
        if (latest.closePrice() == null || latest.closePrice() <= 0) return null;
        if (latest.tradeStatus() != null && latest.tradeStatus() != 1) return null;
        if (latest.volume() == null || latest.amount() == null) return null;

        List<Double> closes = new ArrayList<>();
        for (StockDaily r : history) if (r.closePrice() != null) closes.add(r.closePrice());
        if (closes.size() < 30) return null;

        Double ma5 = IndicatorMath.movingAverage(closes, 5);
        Double ma10 = IndicatorMath.movingAverage(closes, 10);
        Double ma20 = IndicatorMath.movingAverage(closes, 20);
        Double ma60 = IndicatorMath.movingAverage(closes, 60);
        Double ma120 = IndicatorMath.movingAverage(closes, 120);
        Double volumeRatio = IndicatorMath.volumeRatio(history, 20);
        Double return20 = IndicatorMath.periodReturn(closes, 20);
        Double return60 = IndicatorMath.periodReturn(closes, 60);
        Double return120 = IndicatorMath.periodReturn(closes, 120);
        Double rsi14 = IndicatorMath.rsi(closes, 14);

        IndicatorMath.BollSeries boll = IndicatorMath.boll(closes, config.bollPeriod(), config.bollStd());
        IndicatorMath.MacdSeries macd = IndicatorMath.macd(closes,
                config.macdFastPeriod(), config.macdSlowPeriod(), config.macdSignalPeriod());
        IndicatorMath.KdjSeries kdj = IndicatorMath.kdj(history,
                config.kdjPeriod(), config.kdjKSmoothing(), config.kdjDSmoothing());

        Double bollUpper = last(boll.upper());
        Double bollMiddle = last(boll.middle());
        Double bollLower = last(boll.lower());
        Double dif = last(macd.dif());
        Double dea = last(macd.dea());
        Double macdHist = last(macd.hist());
        Double kValue = last(kdj.k());
        Double dValue = last(kdj.d());
        Double jValue = last(kdj.j());

        Double prevDif = secondLast(macd.dif());
        Double prevDea = secondLast(macd.dea());
        Double prevK = secondLast(kdj.k());
        Double prevD = secondLast(kdj.d());

        String macdSignal = IndicatorMath.crossSignal(prevDif, prevDea, dif, dea);
        String kdjSignal = IndicatorMath.crossSignal(prevK, prevD, kValue, dValue);
        Integer macdGoldenDays = IndicatorMath.lastCrossAge(macd.dif(), macd.dea(), "golden_cross");
        Integer macdDeathDays = IndicatorMath.lastCrossAge(macd.dif(), macd.dea(), "death_cross");
        Integer kdjGoldenDays = IndicatorMath.lastCrossAge(kdj.k(), kdj.d(), "golden_cross");
        Integer kdjDeathDays = IndicatorMath.lastCrossAge(kdj.k(), kdj.d(), "death_cross");

        IndicatorMath.BollStatus bollStatus = IndicatorMath.bollStatus(latest.closePrice(), bollUpper, bollMiddle, bollLower);
        double amplitude = IndicatorMath.amplitude(latest);
        double score = IndicatorMath.scoreCandidate(
                latest.pctChange() == null ? 0.0 : latest.pctChange(),
                return20, return60, return120, volumeRatio, amplitude, macdHist, bollStatus.percentB());

        return new IndicatorSnapshot(
                code, latest.tradeDate(),
                latest.closePrice(),
                latest.pctChange() == null ? 0.0 : latest.pctChange(),
                amplitude,
                latest.turn() == null ? 0.0 : latest.turn(),
                latest.volume(),
                latest.amount() == null ? 0.0 : latest.amount(),
                ma5, ma10, ma20, ma60, ma120,
                volumeRatio, return20, return60, return120, rsi14,
                kValue, dValue, jValue, kdjSignal, kdjGoldenDays, kdjDeathDays,
                dif, dea, macdHist, macdSignal, macdGoldenDays, macdDeathDays,
                bollUpper, bollMiddle, bollLower, bollStatus.width(), bollStatus.percentB(), bollStatus.position(),
                score, latest.isStStock()
        );
    }

    /** 计算 K 线图叠加所需的全序列指标。 */
    public IndicatorSeries buildSeries(List<StockDaily> history, IndicatorConfig config) {
        if (history == null || history.isEmpty()) {
            return new IndicatorSeries(Map.of(), List.of(), List.of(), List.of(),
                    List.of(), List.of(), List.of(), List.of(), List.of(), List.of(), List.of());
        }
        List<Double> closes = new ArrayList<>(history.size());
        for (StockDaily r : history) closes.add(r.closePrice());

        Map<Integer, List<Double>> maSeries = new HashMap<>();
        if (config.showMa() && config.maPeriods() != null) {
            for (int period : config.maPeriods()) {
                maSeries.put(period, IndicatorMath.rollingMean(closes, period));
            }
        }
        List<Double> bollUpper = List.of(), bollMiddle = List.of(), bollLower = List.of();
        if (config.showBoll()) {
            IndicatorMath.BollSeries boll = IndicatorMath.boll(closes, config.bollPeriod(), config.bollStd());
            bollUpper = boll.upper();
            bollMiddle = boll.middle();
            bollLower = boll.lower();
        }
        List<Double> dif = List.of(), dea = List.of(), hist = List.of();
        if (config.showMacd()) {
            IndicatorMath.MacdSeries macd = IndicatorMath.macd(closes,
                    config.macdFastPeriod(), config.macdSlowPeriod(), config.macdSignalPeriod());
            dif = macd.dif();
            dea = macd.dea();
            hist = macd.hist();
        }
        List<Double> k = List.of(), d = List.of(), j = List.of();
        if (config.showKdj()) {
            IndicatorMath.KdjSeries kdj = IndicatorMath.kdj(history,
                    config.kdjPeriod(), config.kdjKSmoothing(), config.kdjDSmoothing());
            k = kdj.k();
            d = kdj.d();
            j = kdj.j();
        }
        List<Double> rsi = new ArrayList<>(history.size());
        for (int i = 0; i < closes.size(); i++) {
            rsi.add(i + 1 < 14 ? null : IndicatorMath.rsi(closes.subList(0, i + 1), 14));
        }
        return new IndicatorSeries(maSeries, bollUpper, bollMiddle, bollLower, dif, dea, hist, k, d, j, rsi);
    }

    private static Double last(List<Double> series) {
        return series.isEmpty() ? null : series.get(series.size() - 1);
    }

    private static Double secondLast(List<Double> series) {
        return series.size() < 2 ? null : series.get(series.size() - 2);
    }
}
