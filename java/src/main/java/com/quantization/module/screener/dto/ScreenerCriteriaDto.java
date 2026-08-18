package com.quantization.module.screener.dto;

import java.time.LocalDate;

/**
 * 选股条件 DTO，包含价格、涨跌幅、换手率、技术指标和交叉信号等多维度筛选条件。
 * 所有数值字段可为 null，表示该条件不限制。
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
        String sortBy
) {
}
