package com.quantization.module.indicator;

import com.quantization.module.stock.StockDaily;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 指标引擎：基于 {@link IndicatorMath} 组合，提供候选快照与全序列计算。
 * <p>
 * 采用注册表模式：持有 {@code Map<String, IndicatorCalculator>}，所有
 * {@link IndicatorCalculator} bean 由 Spring 自动注入并按 {@link IndicatorCalculator#name()}
 * 注册。{@link #buildSnapshot} 遍历注册表依次调用各计算器填充
 * {@link IndicatorSnapshotBuilder}，最后统一构建不可变快照。
 * <p>
 * 新增指标只需实现 {@link IndicatorCalculator} 并加 {@code @Component}，无需修改本类。
 * 高内聚：所有技术指标计算集中于此模块，供 dashboard/screener/backtest/chart 复用。
 */
@Slf4j
@Service
public class IndicatorEngine {

    private final Map<String, IndicatorCalculator> registry;

    /**
     * Spring 注入构造函数 — 自动收集所有 {@link IndicatorCalculator} bean 并注册。
     *
     * @param calculators Spring 注入的全部指标计算器
     */
    @Autowired
    public IndicatorEngine(List<IndicatorCalculator> calculators) {
        this.registry = new LinkedHashMap<>();
        for (IndicatorCalculator calculator : calculators) {
            String key = calculator.name();
            if (this.registry.containsKey(key)) {
                log.warn("[indicator] 计算器名称冲突，覆盖已有：{}", key);
            }
            this.registry.put(key, calculator);
        }
        log.info("[indicator] 已注册 {} 个指标计算器：{}", registry.size(), registry.keySet());
    }

    /**
     * 测试友好无参构造函数 — 以内置默认计算器初始化注册表，
     * 供不依赖 Spring 容器的单元测试使用（如 {@code new IndicatorEngine()}）。
     */
    public IndicatorEngine() {
        this(List.of(
                new com.quantization.module.indicator.calculator.MaCalculator(),
                new com.quantization.module.indicator.calculator.RsiCalculator(),
                new com.quantization.module.indicator.calculator.VolumeRatioCalculator(),
                new com.quantization.module.indicator.calculator.ReturnCalculator(),
                new com.quantization.module.indicator.calculator.KdjCalculator(),
                new com.quantization.module.indicator.calculator.MacdCalculator(),
                new com.quantization.module.indicator.calculator.BollCalculator()
        ));
    }

    /**
     * 构建单只股票在最新交易日的指标快照（与原 Python _build_candidate 对齐）。
     * 返回 null 表示数据不足或不可交易。
     */
    public IndicatorSnapshot buildSnapshot(String code, List<StockDaily> history, IndicatorConfig config) {
        if (history == null || history.size() < 30) {
            log.debug("指標計算跳過：歷史數據不足 {} < 30, code={}", history == null ? 0 : history.size(), code);
            return null;
        }
        StockDaily latest = history.get(history.size() - 1);
        if (latest.closePrice() == null || latest.closePrice() <= 0) {
            log.debug("指標計算跳過：收盤價無效 {}, code={}", latest.closePrice(), code);
            return null;
        }
        if (latest.tradeStatus() != null && latest.tradeStatus() != 1) {
            log.debug("指標計算跳過：非正常交易狀態 {}, code={}", latest.tradeStatus(), code);
            return null;
        }
        if (latest.volume() == null || latest.amount() == null) {
            log.debug("指標計算跳過：成交量/成交額為 null, code={}", code);
            return null;
        }

        List<Double> closes = new ArrayList<>();
        for (StockDaily r : history) if (r.closePrice() != null) closes.add(r.closePrice());
        if (closes.size() < 30) {
            log.debug("指標計算跳過：有效收盤價不足 {} < 30, code={}", closes.size(), code);
            return null;
        }

        // 基础字段 + 预计算上下文由引擎设置
        double amplitude = IndicatorMath.amplitude(latest);
        IndicatorSnapshotBuilder builder = new IndicatorSnapshotBuilder();
        builder.code(code);
        builder.tradeDate(latest.tradeDate());
        builder.closePrice(latest.closePrice());
        builder.pctChange(latest.pctChange() == null ? 0.0 : latest.pctChange());
        builder.amplitude(amplitude);
        builder.turn(latest.turn() == null ? 0.0 : latest.turn());
        builder.volume(latest.volume());
        builder.amount(latest.amount() == null ? 0.0 : latest.amount());
        builder.st(latest.isStStock());
        builder.closes(closes);
        builder.config(config);

        // 遍历注册表，各计算器填充对应指标字段
        int index = history.size() - 1;
        for (IndicatorCalculator calculator : registry.values()) {
            calculator.calculate(builder, history, index);
        }

        // 评分为复合指标，依赖多个计算器结果，在所有计算器之后统一计算
        double score = IndicatorMath.scoreCandidate(
                builder.pctChange(),
                builder.return20(), builder.return60(), builder.return120(),
                builder.volumeRatio(), amplitude,
                builder.macdHist(), builder.bollPercentB());
        builder.score(score);

        return builder.build();
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
}
