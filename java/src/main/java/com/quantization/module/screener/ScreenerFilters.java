package com.quantization.module.screener;

import com.quantization.module.indicator.IndicatorSnapshot;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import com.quantization.module.screener.dto.ScreenerCriteriaDto.CrossFilter;
import com.quantization.module.screener.dto.ScreenerCriteriaDto.MaFilter;
import com.quantization.module.screener.dto.ScreenerCriteriaDto.MomentumFilter;
import com.quantization.module.screener.dto.ScreenerCriteriaDto.PctChangeFilter;
import com.quantization.module.screener.dto.ScreenerCriteriaDto.PriceFilter;
import com.quantization.module.screener.dto.ScreenerCriteriaDto.TechnicalFilter;
import com.quantization.module.screener.dto.ScreenerCriteriaDto.TurnoverFilter;
import com.quantization.module.screener.dto.ScreenerCriteriaDto.VolumeFilter;

import java.util.List;
import java.util.Map;

/**
 * 候选与条件的匹配判定（与原 Python _candidate_matches_criteria 对齐）。
 *
 * <p>嵌套重構（P5）：改用 {@link ScreenerCriteriaDto} 的嵌套視圖訪問器
 * （{@code priceFilter()}、{@code momentumFilter()} 等）按域分組判定，
 * 提升可讀性；行為與原扁平字段版本完全一致。
 */
public final class ScreenerFilters {
    private ScreenerFilters() {}

    public static boolean matches(IndicatorSnapshot s, ScreenerCriteriaDto c) {
        return matches(s, c, Map.of());
    }

    public static boolean matches(IndicatorSnapshot s, ScreenerCriteriaDto c, Map<String, String> industryMap) {
        if (Boolean.TRUE.equals(c.excludeSt()) && s.isSt()) return false;
        List<String> industries = c.industries();
        if (industries != null && !industries.isEmpty()) {
            String stockIndustry = industryMap.get(s.code());
            if (stockIndustry == null || !industries.contains(stockIndustry)) return false;
        }

        PriceFilter price = c.priceFilter();
        if (!between(s.closePrice(), price.min(), price.max())) return false;

        PctChangeFilter pct = c.pctChangeFilter();
        if (!between(s.pctChange(), pct.min(), pct.max())) return false;

        TurnoverFilter turnover = c.turnoverFilter();
        if (!between(s.turn(), turnover.minTurn(), turnover.maxTurn())) return false;
        if (!between(s.amplitude(), turnover.minAmplitude(), turnover.maxAmplitude())) return false;

        VolumeFilter volume = c.volumeFilter();
        if (volume.minVolume() != null && s.volume() < volume.minVolume()) return false;
        if (volume.minAmount() != null && s.amount() < volume.minAmount()) return false;
        if (!betweenOpt(s.volumeRatio(), volume.minVolumeRatio(), volume.maxVolumeRatio())) return false;

        MomentumFilter momentum = c.momentumFilter();
        if (!betweenOpt(s.return20(), momentum.minReturn20(), momentum.maxReturn20())) return false;
        if (!betweenOpt(s.return60(), momentum.minReturn60(), momentum.maxReturn60())) return false;
        if (!betweenOpt(s.return120(), momentum.minReturn120(), momentum.maxReturn120())) return false;

        TechnicalFilter tech = c.technicalFilter();
        if (!betweenOpt(s.rsi14(), tech.minRsi14(), tech.maxRsi14())) return false;
        if (!betweenOpt(s.kValue(), tech.minKValue(), tech.maxKValue())) return false;
        if (!betweenOpt(s.dValue(), tech.minDValue(), tech.maxDValue())) return false;
        if (!betweenOpt(s.jValue(), tech.minJValue(), tech.maxJValue())) return false;
        if (!betweenOpt(s.macdHist(), tech.minMacdHist(), tech.maxMacdHist())) return false;
        if (!betweenOpt(s.bollWidth(), tech.minBollWidth(), tech.maxBollWidth())) return false;
        if (!betweenOpt(s.bollPercentB(), tech.minBollPercentB(), tech.maxBollPercentB())) return false;

        CrossFilter cross = c.crossFilter();
        if (cross.macdCrossSignal() != null && !"any".equals(cross.macdCrossSignal())
                && !matchesCrossFilter(cross.macdCrossSignal(), s.macdCrossSignal(), cross.macdCrossWithinDays(),
                s.macdGoldenCrossDaysAgo(), s.macdDeathCrossDaysAgo())) return false;
        if (cross.kdjCrossSignal() != null && !"any".equals(cross.kdjCrossSignal())
                && !matchesCrossFilter(cross.kdjCrossSignal(), s.kdjCrossSignal(), cross.kdjCrossWithinDays(),
                s.kdjGoldenCrossDaysAgo(), s.kdjDeathCrossDaysAgo())) return false;

        if (c.bollFilter().bollPosition() != null
                && !"any".equals(c.bollFilter().bollPosition())
                && !c.bollFilter().bollPosition().equals(s.bollPosition())) return false;

        MaFilter ma = c.maFilter();
        if (Boolean.TRUE.equals(ma.priceAboveMa5()) && (s.ma5() == null || s.closePrice() <= s.ma5())) return false;
        if (Boolean.TRUE.equals(ma.priceAboveMa20()) && (s.ma20() == null || s.closePrice() <= s.ma20())) return false;
        if (Boolean.TRUE.equals(ma.priceAboveMa60()) && (s.ma60() == null || s.closePrice() <= s.ma60())) return false;
        if (Boolean.TRUE.equals(ma.ma5AboveMa20()) && (s.ma5() == null || s.ma20() == null || s.ma5() <= s.ma20())) return false;
        if (Boolean.TRUE.equals(ma.ma20AboveMa60()) && (s.ma20() == null || s.ma60() == null || s.ma20() <= s.ma60())) return false;
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
