package com.quantization.module.indicator;

import com.quantization.module.stock.StockDaily;

import java.time.LocalDate;
import java.util.List;

/**
 * 指标快照可变构建器 — 在 {@link IndicatorEngine#buildSnapshot} 中由各
 * {@link IndicatorCalculator} 协作填充，最终通过 {@link #build()} 构建不可变的
 * {@link IndicatorSnapshot}。
 * <p>
 * 基础字段（code/tradeDate/closePrice 等）由引擎从最新行情直接设置；
 * 技术指标字段（MA/RSI/KDJ/MACD/BOLL 等）由各计算器填充；
 * score 由引擎在所有计算器执行后统一计算。
 */
public class IndicatorSnapshotBuilder {

    // ===== 基础字段（引擎设置） =====
    private String code;
    private LocalDate tradeDate;
    private double closePrice;
    private double pctChange;
    private double amplitude;
    private double turn;
    private long volume;
    private double amount;
    private boolean st;

    // ===== 预计算上下文（引擎设置，供计算器读取） =====
    /** 过滤 null 后的收盘价序列（与原 buildSnapshot 中 closes 一致）。 */
    private List<Double> closes;
    /** 指标计算配置。 */
    private IndicatorConfig config;

    // ===== 技术指标字段（计算器填充） =====
    private Double ma5;
    private Double ma10;
    private Double ma20;
    private Double ma60;
    private Double ma120;
    private Double volumeRatio;
    private Double return20;
    private Double return60;
    private Double return120;
    private Double rsi14;
    private Double kValue;
    private Double dValue;
    private Double jValue;
    private String kdjCrossSignal;
    private Integer kdjGoldenCrossDaysAgo;
    private Integer kdjDeathCrossDaysAgo;
    private Double dif;
    private Double dea;
    private Double macdHist;
    private String macdCrossSignal;
    private Integer macdGoldenCrossDaysAgo;
    private Integer macdDeathCrossDaysAgo;
    private Double bollUpper;
    private Double bollMiddle;
    private Double bollLower;
    private Double bollWidth;
    private Double bollPercentB;
    private String bollPosition;

    // ===== 评分（引擎在计算器之后计算） =====
    private double score;

    // --- 基础字段 getters/setters ---
    public String code() { return code; }
    public void code(String code) { this.code = code; }

    public LocalDate tradeDate() { return tradeDate; }
    public void tradeDate(LocalDate tradeDate) { this.tradeDate = tradeDate; }

    public double closePrice() { return closePrice; }
    public void closePrice(double closePrice) { this.closePrice = closePrice; }

    public double pctChange() { return pctChange; }
    public void pctChange(double pctChange) { this.pctChange = pctChange; }

    public double amplitude() { return amplitude; }
    public void amplitude(double amplitude) { this.amplitude = amplitude; }

    public double turn() { return turn; }
    public void turn(double turn) { this.turn = turn; }

    public long volume() { return volume; }
    public void volume(long volume) { this.volume = volume; }

    public double amount() { return amount; }
    public void amount(double amount) { this.amount = amount; }

    public boolean st() { return st; }
    public void st(boolean st) { this.st = st; }

    // --- 上下文 getters/setters ---
    public List<Double> closes() { return closes; }
    public void closes(List<Double> closes) { this.closes = closes; }

    public IndicatorConfig config() { return config; }
    public void config(IndicatorConfig config) { this.config = config; }

    // --- 指标字段 getters/setters ---
    public Double ma5() { return ma5; }
    public void ma5(Double ma5) { this.ma5 = ma5; }

    public Double ma10() { return ma10; }
    public void ma10(Double ma10) { this.ma10 = ma10; }

    public Double ma20() { return ma20; }
    public void ma20(Double ma20) { this.ma20 = ma20; }

    public Double ma60() { return ma60; }
    public void ma60(Double ma60) { this.ma60 = ma60; }

    public Double ma120() { return ma120; }
    public void ma120(Double ma120) { this.ma120 = ma120; }

    public Double volumeRatio() { return volumeRatio; }
    public void volumeRatio(Double volumeRatio) { this.volumeRatio = volumeRatio; }

    public Double return20() { return return20; }
    public void return20(Double return20) { this.return20 = return20; }

    public Double return60() { return return60; }
    public void return60(Double return60) { this.return60 = return60; }

    public Double return120() { return return120; }
    public void return120(Double return120) { this.return120 = return120; }

    public Double rsi14() { return rsi14; }
    public void rsi14(Double rsi14) { this.rsi14 = rsi14; }

    public Double kValue() { return kValue; }
    public void kValue(Double kValue) { this.kValue = kValue; }

    public Double dValue() { return dValue; }
    public void dValue(Double dValue) { this.dValue = dValue; }

    public Double jValue() { return jValue; }
    public void jValue(Double jValue) { this.jValue = jValue; }

    public String kdjCrossSignal() { return kdjCrossSignal; }
    public void kdjCrossSignal(String kdjCrossSignal) { this.kdjCrossSignal = kdjCrossSignal; }

    public Integer kdjGoldenCrossDaysAgo() { return kdjGoldenCrossDaysAgo; }
    public void kdjGoldenCrossDaysAgo(Integer kdjGoldenCrossDaysAgo) { this.kdjGoldenCrossDaysAgo = kdjGoldenCrossDaysAgo; }

    public Integer kdjDeathCrossDaysAgo() { return kdjDeathCrossDaysAgo; }
    public void kdjDeathCrossDaysAgo(Integer kdjDeathCrossDaysAgo) { this.kdjDeathCrossDaysAgo = kdjDeathCrossDaysAgo; }

    public Double dif() { return dif; }
    public void dif(Double dif) { this.dif = dif; }

    public Double dea() { return dea; }
    public void dea(Double dea) { this.dea = dea; }

    public Double macdHist() { return macdHist; }
    public void macdHist(Double macdHist) { this.macdHist = macdHist; }

    public String macdCrossSignal() { return macdCrossSignal; }
    public void macdCrossSignal(String macdCrossSignal) { this.macdCrossSignal = macdCrossSignal; }

    public Integer macdGoldenCrossDaysAgo() { return macdGoldenCrossDaysAgo; }
    public void macdGoldenCrossDaysAgo(Integer macdGoldenCrossDaysAgo) { this.macdGoldenCrossDaysAgo = macdGoldenCrossDaysAgo; }

    public Integer macdDeathCrossDaysAgo() { return macdDeathCrossDaysAgo; }
    public void macdDeathCrossDaysAgo(Integer macdDeathCrossDaysAgo) { this.macdDeathCrossDaysAgo = macdDeathCrossDaysAgo; }

    public Double bollUpper() { return bollUpper; }
    public void bollUpper(Double bollUpper) { this.bollUpper = bollUpper; }

    public Double bollMiddle() { return bollMiddle; }
    public void bollMiddle(Double bollMiddle) { this.bollMiddle = bollMiddle; }

    public Double bollLower() { return bollLower; }
    public void bollLower(Double bollLower) { this.bollLower = bollLower; }

    public Double bollWidth() { return bollWidth; }
    public void bollWidth(Double bollWidth) { this.bollWidth = bollWidth; }

    public Double bollPercentB() { return bollPercentB; }
    public void bollPercentB(Double bollPercentB) { this.bollPercentB = bollPercentB; }

    public String bollPosition() { return bollPosition; }
    public void bollPosition(String bollPosition) { this.bollPosition = bollPosition; }

    public double score() { return score; }
    public void score(double score) { this.score = score; }

    // --- 序列辅助 ---
    /** 取序列最后一个非空判断后的元素，空序列返回 null。 */
    public static Double last(List<Double> series) {
        return series.isEmpty() ? null : series.get(series.size() - 1);
    }

    /** 取序列倒数第二个元素，长度不足返回 null。 */
    public static Double secondLast(List<Double> series) {
        return series.size() < 2 ? null : series.get(series.size() - 2);
    }

    /**
     * 构建不可变快照。字段顺序与 {@link IndicatorSnapshot} 构造函数完全一致。
     */
    public IndicatorSnapshot build() {
        return new IndicatorSnapshot(
                code, tradeDate,
                closePrice,
                pctChange,
                amplitude,
                turn,
                volume,
                amount,
                ma5, ma10, ma20, ma60, ma120,
                volumeRatio, return20, return60, return120, rsi14,
                kValue, dValue, jValue, kdjCrossSignal, kdjGoldenCrossDaysAgo, kdjDeathCrossDaysAgo,
                dif, dea, macdHist, macdCrossSignal, macdGoldenCrossDaysAgo, macdDeathCrossDaysAgo,
                bollUpper, bollMiddle, bollLower, bollWidth, bollPercentB, bollPosition,
                score, st
        );
    }
}
