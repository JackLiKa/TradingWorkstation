package com.quantization.module.screener.dto;

import java.time.LocalDate;
import java.util.List;

/**
 * 选股条件 DTO，包含价格、涨跌幅、换手率、技术指标、交叉信号与行业等多维度筛选条件。
 * 所有数值字段可为 null，表示该条件不限制。
 *
 * <p>嵌套重構（P5）：保留全部 49 個扁平字段以維持序列化格式與 API 契約不變，
 * 同時提供按域分組的嵌套子記錄視圖訪問器（{@link #priceFilter()}、
 * {@link #momentumFilter()} 等），供 ScreenerFilters / ScreenerCore 等消費端
 * 以語義化方式訪問分組條件。嵌套視圖為只讀派生視圖，不參與 Jackson 序列化。
 */
public record ScreenerCriteriaDto(
        LocalDate asOfDate,
        Integer adjustflag,
        Double minClose,
        Double maxClose,
        Double minPctChange,
        Double maxPctChange,
        Double minTurn,
        Double maxTurn,
        Double minAmplitude,
        Double maxAmplitude,
        Long minVolume,
        Double minAmount,
        Double minVolumeRatio,
        Double maxVolumeRatio,
        Double minReturn20,
        Double maxReturn20,
        Double minReturn60,
        Double maxReturn60,
        Double minReturn120,
        Double maxReturn120,
        Double minRsi14,
        Double maxRsi14,
        Double minKValue,
        Double maxKValue,
        Double minDValue,
        Double maxDValue,
        Double minJValue,
        Double maxJValue,
        Double minMacdHist,
        Double maxMacdHist,
        Double minBollWidth,
        Double maxBollWidth,
        Double minBollPercentB,
        Double maxBollPercentB,
        Boolean priceAboveMa5,
        Boolean priceAboveMa20,
        Boolean priceAboveMa60,
        Boolean ma5AboveMa20,
        Boolean ma20AboveMa60,
        String macdCrossSignal,
        Integer macdCrossWithinDays,
        String kdjCrossSignal,
        Integer kdjCrossWithinDays,
        String bollPosition,
        Boolean excludeSt,
        Integer maxResults,
        String sortBy,
        List<String> industries
) {

    // =========================================================================
    // 嵌套子記錄（按域分組的視圖類型）
    // =========================================================================

    /** 價格區間過濾（minClose / maxClose）。 */
    public record PriceFilter(Double min, Double max) {}

    /** 漲跌幅區間過濾（minPctChange / maxPctChange）。 */
    public record PctChangeFilter(Double min, Double max) {}

    /** 換手率與振幅過濾（minTurn / maxTurn / minAmplitude / maxAmplitude）。 */
    public record TurnoverFilter(Double minTurn, Double maxTurn, Double minAmplitude, Double maxAmplitude) {}

    /** 成交量與成交額過濾（minVolume / minAmount / minVolumeRatio / maxVolumeRatio）。 */
    public record VolumeFilter(Long minVolume, Double minAmount, Double minVolumeRatio, Double maxVolumeRatio) {}

    /** 動量過濾（20/60/120 日漲幅區間）。 */
    public record MomentumFilter(
            Double minReturn20, Double maxReturn20,
            Double minReturn60, Double maxReturn60,
            Double minReturn120, Double maxReturn120) {}

    /** 技術指標區間過濾（RSI / KDJ / MACD 柱 / BOLL 帶寬 / BOLL%B）。 */
    public record TechnicalFilter(
            Double minRsi14, Double maxRsi14,
            Double minKValue, Double maxKValue,
            Double minDValue, Double maxDValue,
            Double minJValue, Double maxJValue,
            Double minMacdHist, Double maxMacdHist,
            Double minBollWidth, Double maxBollWidth,
            Double minBollPercentB, Double maxBollPercentB) {}

    /** 均線排列過濾（價格站上均線、均線多頭排列）。 */
    public record MaFilter(
            Boolean priceAboveMa5, Boolean priceAboveMa20, Boolean priceAboveMa60,
            Boolean ma5AboveMa20, Boolean ma20AboveMa60) {}

    /** 交叉信號過濾（MACD / KDJ 金叉死叉 + 窗口天數）。 */
    public record CrossFilter(
            String macdCrossSignal, Integer macdCrossWithinDays,
            String kdjCrossSignal, Integer kdjCrossWithinDays) {}

    /** BOLL 位置過濾（upper_zone / lower_zone / ...）。 */
    public record BollFilter(String bollPosition) {}

    // =========================================================================
    // 嵌套視圖訪問器（只讀派生，不改變序列化格式）
    // =========================================================================

    public PriceFilter priceFilter() {
        return new PriceFilter(minClose, maxClose);
    }

    public PctChangeFilter pctChangeFilter() {
        return new PctChangeFilter(minPctChange, maxPctChange);
    }

    public TurnoverFilter turnoverFilter() {
        return new TurnoverFilter(minTurn, maxTurn, minAmplitude, maxAmplitude);
    }

    public VolumeFilter volumeFilter() {
        return new VolumeFilter(minVolume, minAmount, minVolumeRatio, maxVolumeRatio);
    }

    public MomentumFilter momentumFilter() {
        return new MomentumFilter(minReturn20, maxReturn20, minReturn60, maxReturn60, minReturn120, maxReturn120);
    }

    public TechnicalFilter technicalFilter() {
        return new TechnicalFilter(
                minRsi14, maxRsi14,
                minKValue, maxKValue,
                minDValue, maxDValue,
                minJValue, maxJValue,
                minMacdHist, maxMacdHist,
                minBollWidth, maxBollWidth,
                minBollPercentB, maxBollPercentB);
    }

    public MaFilter maFilter() {
        return new MaFilter(priceAboveMa5, priceAboveMa20, priceAboveMa60, ma5AboveMa20, ma20AboveMa60);
    }

    public CrossFilter crossFilter() {
        return new CrossFilter(macdCrossSignal, macdCrossWithinDays, kdjCrossSignal, kdjCrossWithinDays);
    }

    public BollFilter bollFilter() {
        return new BollFilter(bollPosition);
    }
}
