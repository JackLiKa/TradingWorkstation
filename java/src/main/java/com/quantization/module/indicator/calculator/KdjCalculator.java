package com.quantization.module.indicator.calculator;

import com.quantization.module.indicator.IndicatorCalculator;
import com.quantization.module.indicator.IndicatorConfig;
import com.quantization.module.indicator.IndicatorMath;
import com.quantization.module.indicator.IndicatorSnapshotBuilder;
import com.quantization.module.stock.StockDaily;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * KDJ 指标计算器 — 计算 K/D/J 最新值、交叉信号与金叉/死叉距今天数。
 * 逻辑与原 {@code IndicatorEngine.buildSnapshot} 中 KDJ 部分完全一致。
 */
@Component
public class KdjCalculator implements IndicatorCalculator {

    @Override
    public String name() {
        return "KDJ";
    }

    @Override
    public void calculate(IndicatorSnapshotBuilder builder, List<StockDaily> history, int index) {
        IndicatorConfig config = builder.config();
        IndicatorMath.KdjSeries kdj = IndicatorMath.kdj(history,
                config.kdjPeriod(), config.kdjKSmoothing(), config.kdjDSmoothing());

        Double kValue = IndicatorSnapshotBuilder.last(kdj.k());
        Double dValue = IndicatorSnapshotBuilder.last(kdj.d());
        Double jValue = IndicatorSnapshotBuilder.last(kdj.j());

        Double prevK = IndicatorSnapshotBuilder.secondLast(kdj.k());
        Double prevD = IndicatorSnapshotBuilder.secondLast(kdj.d());

        String kdjSignal = IndicatorMath.crossSignal(prevK, prevD, kValue, dValue);
        Integer kdjGoldenDays = IndicatorMath.lastCrossAge(kdj.k(), kdj.d(), "golden_cross");
        Integer kdjDeathDays = IndicatorMath.lastCrossAge(kdj.k(), kdj.d(), "death_cross");

        builder.kValue(kValue);
        builder.dValue(dValue);
        builder.jValue(jValue);
        builder.kdjCrossSignal(kdjSignal);
        builder.kdjGoldenCrossDaysAgo(kdjGoldenDays);
        builder.kdjDeathCrossDaysAgo(kdjDeathDays);
    }
}
