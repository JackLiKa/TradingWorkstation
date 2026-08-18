package com.quantization.module.indicator;

import com.quantization.common.util.DecimalUtils;
import com.quantization.module.stock.StockDaily;

import java.util.ArrayList;
import java.util.List;

/**
 * 指标数学计算（忠实移植原 Python dashboard_service 中的静态方法）。
 * 全部使用 double 运算，与原版 round(..., 4) 对齐。
 */
public final class IndicatorMath {
    private IndicatorMath() {}

    public static Double movingAverage(List<Double> values, int period) {
        if (values.size() < period) return null;
        return DecimalUtils.round(DecimalUtils.mean(values.subList(values.size() - period, values.size())), 4);
    }

    public static Double periodReturn(List<Double> values, int period) {
        if (values.size() <= period) return null;
        double base = values.get(values.size() - period - 1);
        if (base == 0) return null;
        return DecimalUtils.round((values.get(values.size() - 1) / base - 1) * 100, 4);
    }

    public static Double volumeRatio(List<StockDaily> history, int period) {
        List<Long> volumes = new ArrayList<>();
        for (StockDaily r : history) if (r.volume() != null) volumes.add(r.volume());
        if (volumes.size() <= period) return null;
        List<Long> window = volumes.subList(volumes.size() - period - 1, volumes.size() - 1);
        double baseline = 0;
        for (Long v : window) baseline += v;
        baseline /= period;
        if (baseline <= 0) return null;
        return DecimalUtils.round(volumes.get(volumes.size() - 1) / baseline, 4);
    }

    public static double amplitude(StockDaily record) {
        if (record.highPrice() == null || record.lowPrice() == null) return 0.0;
        double base = record.preclosePrice() != null ? record.preclosePrice()
                : (record.closePrice() != null ? record.closePrice() : 0.0);
        if (base <= 0) return 0.0;
        return DecimalUtils.round((record.highPrice() - record.lowPrice()) / base * 100, 4);
    }

    /** 滚动均值，null 填充前 period-1 位。 */
    public static List<Double> rollingMean(List<Double> values, int period) {
        List<Double> result = new ArrayList<>(values.size());
        for (int i = 0; i < values.size(); i++) {
            if (i + 1 < period) {
                result.add(null);
                continue;
            }
            List<Double> window = values.subList(i + 1 - period, i + 1);
            if (window.stream().anyMatch(java.util.Objects::isNull)) {
                result.add(null);
                continue;
            }
            result.add(DecimalUtils.mean(window));
        }
        return result;
    }

    public static List<Double> ema(List<Double> values, int period) {
        List<Double> result = new ArrayList<>(values.size());
        double multiplier = 2.0 / (period + 1);
        Double previous = null;
        for (Double value : values) {
            if (value == null) {
                result.add(null);
                continue;
            }
            if (previous == null) {
                previous = value;
            } else {
                previous = (value - previous) * multiplier + previous;
            }
            result.add(previous);
        }
        return result;
    }

    public record BollSeries(List<Double> upper, List<Double> middle, List<Double> lower) {}

    public static BollSeries boll(List<Double> closes, int period, double stdFactor) {
        List<Double> middle = rollingMean(closes, period);
        List<Double> upper = new ArrayList<>(closes.size());
        List<Double> lower = new ArrayList<>(closes.size());
        for (int i = 0; i < closes.size(); i++) {
            if (i + 1 < period || closes.get(i) == null) {
                upper.add(null);
                lower.add(null);
                continue;
            }
            List<Double> window = closes.subList(i + 1 - period, i + 1);
            if (window.stream().anyMatch(java.util.Objects::isNull)) {
                upper.add(null);
                lower.add(null);
                continue;
            }
            Double midValue = middle.get(i);
            if (midValue == null) {
                upper.add(null);
                lower.add(null);
                continue;
            }
            double stddev = DecimalUtils.pstdev(window);
            upper.add(midValue + stddev * stdFactor);
            lower.add(midValue - stddev * stdFactor);
        }
        return new BollSeries(upper, middle, lower);
    }

    public record MacdSeries(List<Double> dif, List<Double> dea, List<Double> hist) {}

    public static MacdSeries macd(List<Double> closes, int fast, int slow, int signal) {
        List<Double> emaFast = ema(closes, fast);
        List<Double> emaSlow = ema(closes, slow);
        List<Double> dif = new ArrayList<>(closes.size());
        for (int i = 0; i < closes.size(); i++) {
            Double f = emaFast.get(i);
            Double s = emaSlow.get(i);
            dif.add((f == null || s == null) ? null : f - s);
        }
        List<Double> dea = ema(dif, signal);
        List<Double> hist = new ArrayList<>(closes.size());
        for (int i = 0; i < closes.size(); i++) {
            Double d = dif.get(i);
            Double e = dea.get(i);
            hist.add((d == null || e == null) ? null : (d - e) * 2);
        }
        return new MacdSeries(dif, dea, hist);
    }

    public record KdjSeries(List<Double> k, List<Double> d, List<Double> j) {}

    public static KdjSeries kdj(List<StockDaily> history, int period, int kSmoothing, int dSmoothing) {
        List<Double> kValues = new ArrayList<>(history.size());
        List<Double> dValues = new ArrayList<>(history.size());
        List<Double> jValues = new ArrayList<>(history.size());
        double previousK = 50.0;
        double previousD = 50.0;
        for (int i = 0; i < history.size(); i++) {
            if (i + 1 < period) {
                kValues.add(null);
                dValues.add(null);
                jValues.add(null);
                continue;
            }
            List<StockDaily> window = history.subList(i + 1 - period, i + 1);
            double highest = Double.NEGATIVE_INFINITY;
            double lowest = Double.POSITIVE_INFINITY;
            boolean hasNull = false;
            for (StockDaily w : window) {
                if (w.highPrice() == null || w.lowPrice() == null) {
                    hasNull = true;
                    break;
                }
                highest = Math.max(highest, w.highPrice());
                lowest = Math.min(lowest, w.lowPrice());
            }
            StockDaily record = history.get(i);
            if (hasNull || record.closePrice() == null) {
                kValues.add(null);
                dValues.add(null);
                jValues.add(null);
                continue;
            }
            double denominator = highest - lowest;
            double rsv = denominator == 0 ? 50.0 : (record.closePrice() - lowest) / denominator * 100;
            double currentK = previousK * (kSmoothing - 1) / kSmoothing + rsv / kSmoothing;
            double currentD = previousD * (dSmoothing - 1) / dSmoothing + currentK / dSmoothing;
            double currentJ = currentK * 3 - currentD * 2;
            previousK = currentK;
            previousD = currentD;
            kValues.add(currentK);
            dValues.add(currentD);
            jValues.add(currentJ);
        }
        return new KdjSeries(kValues, dValues, jValues);
    }

    public static Double rsi(List<Double> values, int period) {
        if (values.size() <= period) return null;
        double gains = 0.0;
        double losses = 0.0;
        for (int i = values.size() - period; i < values.size(); i++) {
            double delta = values.get(i) - values.get(i - 1);
            if (delta > 0) gains += delta;
            else losses += -delta;
        }
        double averageGain = gains / period;
        double averageLoss = losses / period;
        if (averageLoss == 0) return averageGain > 0 ? 100.0 : 50.0;
        double rs = averageGain / averageLoss;
        return DecimalUtils.round(100 - (100 / (1 + rs)), 4);
    }

    public static String crossSignal(Double prevLeft, Double prevRight, Double curLeft, Double curRight) {
        if (prevLeft == null || prevRight == null || curLeft == null || curRight == null) return "any";
        if (prevLeft <= prevRight && curLeft > curRight) return "golden_cross";
        if (prevLeft >= prevRight && curLeft < curRight) return "death_cross";
        return "none";
    }

    public static Integer lastCrossAge(List<Double> left, List<Double> right, String signalName) {
        for (int i = left.size() - 1; i > 0; i--) {
            String signal = crossSignal(left.get(i - 1), right.get(i - 1), left.get(i), right.get(i));
            if (signal.equals(signalName)) return left.size() - 1 - i;
        }
        return null;
    }

    public record BollStatus(Double width, Double percentB, String position) {}

    public static BollStatus bollStatus(double closePrice, Double upper, Double middle, Double lower) {
        if (upper == null || middle == null || lower == null) return new BollStatus(null, null, "any");
        if (middle == 0 || upper.equals(lower)) return new BollStatus(0.0, 50.0, "middle_upper");
        double width = (upper - lower) / middle * 100;
        double percentB = (closePrice - lower) / (upper - lower) * 100;
        String position;
        if (closePrice > upper) position = "above_upper";
        else if (closePrice >= (upper + middle) / 2) position = "upper_zone";
        else if (closePrice >= middle) position = "middle_upper";
        else if (closePrice >= (middle + lower) / 2) position = "middle_lower";
        else if (closePrice >= lower) position = "lower_zone";
        else position = "below_lower";
        return new BollStatus(DecimalUtils.round(width, 4), DecimalUtils.round(percentB, 4), position);
    }

    public static double scoreCandidate(double latestPctChange, Double return20, Double return60,
                                        Double return120, Double volumeRatio, double amplitude,
                                        Double macdHist, Double bollPercentB) {
        return DecimalUtils.round(
                (return20 == null ? 0 : return20) * 0.30
                        + (return60 == null ? 0 : return60) * 0.25
                        + (return120 == null ? 0 : return120) * 0.15
                        + latestPctChange * 0.10
                        + Math.max((volumeRatio == null ? 1.0 : volumeRatio) - 1.0, 0.0) * 10
                        + (macdHist == null ? 0 : macdHist) * 4
                        + (bollPercentB == null ? 50.0 : bollPercentB) * 0.08
                        - amplitude * 0.05,
                4);
    }
}
