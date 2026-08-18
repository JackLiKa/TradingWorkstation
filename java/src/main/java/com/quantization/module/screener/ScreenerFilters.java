package com.quantization.module.screener;

import com.quantization.module.indicator.IndicatorSnapshot;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;

/**
 * 候选与条件的匹配判定（与原 Python _candidate_matches_criteria 对齐）。
 */
public final class ScreenerFilters {
    private ScreenerFilters() {}

    public static boolean matches(IndicatorSnapshot s, ScreenerCriteriaDto c) {
        if (Boolean.TRUE.equals(c.excludeSt()) && s.isSt()) return false;
        if (!between(s.closePrice(), c.minClose(), c.maxClose())) return false;
        if (!between(s.pctChange(), c.minPctChange(), c.maxPctChange())) return false;
        if (!between(s.turn(), c.minTurn(), c.maxTurn())) return false;
        if (!between(s.amplitude(), c.minAmplitude(), c.maxAmplitude())) return false;
        if (c.minVolume() != null && s.volume() < c.minVolume()) return false;
        if (c.minAmount() != null && s.amount() < c.minAmount()) return false;
        if (!betweenOpt(s.volumeRatio(), c.minVolumeRatio(), c.maxVolumeRatio())) return false;
        if (!betweenOpt(s.return20(), c.minReturn20(), c.maxReturn20())) return false;
        if (!betweenOpt(s.return60(), c.minReturn60(), c.maxReturn60())) return false;
        if (!betweenOpt(s.return120(), c.minReturn120(), c.maxReturn120())) return false;
        if (!betweenOpt(s.rsi14(), c.minRsi14(), c.maxRsi14())) return false;
        if (!betweenOpt(s.kValue(), c.minKValue(), c.maxKValue())) return false;
        if (!betweenOpt(s.dValue(), c.minDValue(), c.maxDValue())) return false;
        if (!betweenOpt(s.jValue(), c.minJValue(), c.maxJValue())) return false;
        if (!betweenOpt(s.macdHist(), c.minMacdHist(), c.maxMacdHist())) return false;
        if (!betweenOpt(s.bollWidth(), c.minBollWidth(), c.maxBollWidth())) return false;
        if (!betweenOpt(s.bollPercentB(), c.minBollPercentB(), c.maxBollPercentB())) return false;
        if (c.macdCrossSignal() != null && !"any".equals(c.macdCrossSignal())
                && !matchesCrossFilter(c.macdCrossSignal(), s.macdCrossSignal(), c.macdCrossWithinDays(),
                s.macdGoldenCrossDaysAgo(), s.macdDeathCrossDaysAgo())) return false;
        if (c.kdjCrossSignal() != null && !"any".equals(c.kdjCrossSignal())
                && !matchesCrossFilter(c.kdjCrossSignal(), s.kdjCrossSignal(), c.kdjCrossWithinDays(),
                s.kdjGoldenCrossDaysAgo(), s.kdjDeathCrossDaysAgo())) return false;
        if (c.bollPosition() != null && !"any".equals(c.bollPosition()) && !c.bollPosition().equals(s.bollPosition())) return false;
        if (Boolean.TRUE.equals(c.priceAboveMa5()) && (s.ma5() == null || s.closePrice() <= s.ma5())) return false;
        if (Boolean.TRUE.equals(c.priceAboveMa20()) && (s.ma20() == null || s.closePrice() <= s.ma20())) return false;
        if (Boolean.TRUE.equals(c.priceAboveMa60()) && (s.ma60() == null || s.closePrice() <= s.ma60())) return false;
        if (Boolean.TRUE.equals(c.ma5AboveMa20()) && (s.ma5() == null || s.ma20() == null || s.ma5() <= s.ma20())) return false;
        if (Boolean.TRUE.equals(c.ma20AboveMa60()) && (s.ma20() == null || s.ma60() == null || s.ma20() <= s.ma60())) return false;
        return true;
    }

    private static boolean matchesCrossFilter(String signalName, String currentSignal, Integer withinDays,
                                              Integer goldenDaysAgo, Integer deathDaysAgo) {
        if ("none".equals(signalName)) return "none".equals(currentSignal);
        if (withinDays == null || withinDays <= 0) return signalName.equals(currentSignal);
        Integer daysAgo = "golden_cross".equals(signalName) ? goldenDaysAgo : deathDaysAgo;
        return daysAgo != null && daysAgo < withinDays;
    }

    private static boolean between(double value, Double lower, Double upper) {
        if (lower != null && value < lower) return false;
        if (upper != null && value > upper) return false;
        return true;
    }

    private static boolean betweenOpt(Double value, Double lower, Double upper) {
        return value != null && between(value, lower, upper);
    }
}
