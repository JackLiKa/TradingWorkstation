package com.quantization.test;

import com.quantization.module.screener.dto.ScreenerCriteriaDto;

import java.time.LocalDate;
import java.util.List;

/**
 * ScreenerCriteriaDto 測試構建器 — 簡化 49 字段 record 的構造。
 * 默認所有字段為 null/false，通過 withXxx 方法覆蓋。
 */
public final class CriteriaBuilder {
    private LocalDate asOfDate;
    private Integer adjustflag = 3;
    private Double minClose, maxClose, minPctChange, maxPctChange;
    private Double minTurn, maxTurn, minAmplitude, maxAmplitude;
    private Long minVolume;
    private Double minAmount, minVolumeRatio, maxVolumeRatio;
    private Double minReturn20, maxReturn20, minReturn60, maxReturn60, minReturn120, maxReturn120;
    private Double minRsi14, maxRsi14, minKValue, maxKValue, minDValue, maxDValue, minJValue, maxJValue;
    private Double minMacdHist, maxMacdHist, minBollWidth, maxBollWidth, minBollPercentB, maxBollPercentB;
    private Boolean priceAboveMa5, priceAboveMa20, priceAboveMa60, ma5AboveMa20, ma20AboveMa60;
    private String macdCrossSignal;
    private Integer macdCrossWithinDays;
    private String kdjCrossSignal;
    private Integer kdjCrossWithinDays;
    private String bollPosition;
    private Boolean excludeSt = false;
    private Integer maxResults;
    private String sortBy = "score";

    public CriteriaBuilder() {}

    public static CriteriaBuilder create() { return new CriteriaBuilder(); }

    public CriteriaBuilder asOfDate(LocalDate v) { this.asOfDate = v; return this; }
    public CriteriaBuilder adjustflag(int v) { this.adjustflag = v; return this; }
    public CriteriaBuilder minPctChange(Double v) { this.minPctChange = v; return this; }
    public CriteriaBuilder maxPctChange(Double v) { this.maxPctChange = v; return this; }
    public CriteriaBuilder minTurn(Double v) { this.minTurn = v; return this; }
    public CriteriaBuilder minAmplitude(Double v) { this.minAmplitude = v; return this; }
    public CriteriaBuilder minVolumeRatio(Double v) { this.minVolumeRatio = v; return this; }
    public CriteriaBuilder minReturn20(Double v) { this.minReturn20 = v; return this; }
    public CriteriaBuilder minReturn60(Double v) { this.minReturn60 = v; return this; }
    public CriteriaBuilder minReturn120(Double v) { this.minReturn120 = v; return this; }
    public CriteriaBuilder minRsi14(Double v) { this.minRsi14 = v; return this; }
    public CriteriaBuilder minBollWidth(Double v) { this.minBollWidth = v; return this; }
    public CriteriaBuilder minBollPercentB(Double v) { this.minBollPercentB = v; return this; }
    public CriteriaBuilder macdCrossSignal(String v) { this.macdCrossSignal = v; return this; }
    public CriteriaBuilder macdCrossWithinDays(Integer v) { this.macdCrossWithinDays = v; return this; }
    public CriteriaBuilder kdjCrossSignal(String v) { this.kdjCrossSignal = v; return this; }
    public CriteriaBuilder bollPosition(String v) { this.bollPosition = v; return this; }
    public CriteriaBuilder priceAboveMa20(boolean v) { this.priceAboveMa20 = v; return this; }
    public CriteriaBuilder ma5AboveMa20(boolean v) { this.ma5AboveMa20 = v; return this; }
    public CriteriaBuilder ma20AboveMa60(boolean v) { this.ma20AboveMa60 = v; return this; }
    public CriteriaBuilder excludeSt(boolean v) { this.excludeSt = v; return this; }
    public CriteriaBuilder maxResults(int v) { this.maxResults = v; return this; }
    public CriteriaBuilder sortBy(String v) { this.sortBy = v; return this; }

    public ScreenerCriteriaDto build() {
        return new ScreenerCriteriaDto(
                asOfDate, adjustflag,
                minClose, maxClose, minPctChange, maxPctChange,
                minTurn, maxTurn, minAmplitude, maxAmplitude,
                minVolume, minAmount, minVolumeRatio, maxVolumeRatio,
                minReturn20, maxReturn20, minReturn60, maxReturn60, minReturn120, maxReturn120,
                minRsi14, maxRsi14, minKValue, maxKValue, minDValue, maxDValue, minJValue, maxJValue,
                minMacdHist, maxMacdHist, minBollWidth, maxBollWidth, minBollPercentB, maxBollPercentB,
                priceAboveMa5, priceAboveMa20, priceAboveMa60, ma5AboveMa20, ma20AboveMa60,
                macdCrossSignal, macdCrossWithinDays, kdjCrossSignal, kdjCrossWithinDays,
                bollPosition, excludeSt, maxResults, sortBy, null
        );
    }
}
