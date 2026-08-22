package com.quantization.module.indicator.calculator;

import com.quantization.module.indicator.IndicatorCalculator;
import com.quantization.module.indicator.IndicatorConfig;
import com.quantization.module.indicator.IndicatorMath;
import com.quantization.module.indicator.IndicatorSnapshotBuilder;
import com.quantization.module.stock.StockDaily;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * MACD 指标计算器 — 计算 DIF/DEA/HIST 最新值、交叉信号与金叉/死叉距今天数。
 * 逻辑与原 {@code IndicatorEngine.buildSnapshot} 中 MACD 部分完全一致。
 */
@Component
public class MacdCalculator implements IndicatorCalculator {

    @Override
    public String name() {
        return "MACD";
    }

    @Override
    public void calculate(IndicatorSnapshotBuilder builder, List<StockDaily> history, int index) {
        IndicatorConfig config = builder.config();
        IndicatorMath.MacdSeries macd = IndicatorMath.macd(builder.closes(),
                config.macdFastPeriod(), config.macdSlowPeriod(), config.macdSignalPeriod());

        Double dif = IndicatorSnapshotBuilder.last(macd.dif());
        Double dea = IndicatorSnapshotBuilder.last(macd.dea());
        Double macdHist = IndicatorSnapshotBuilder.last(macd.hist());

        Double prevDif = IndicatorSnapshotBuilder.secondLast(macd.dif());
        Double prevDea = IndicatorSnapshotBuilder.secondLast(macd.dea());

        String macdSignal = IndicatorMath.crossSignal(prevDif, prevDea, dif, dea);
        Integer macdGoldenDays = IndicatorMath.lastCrossAge(macd.dif(), macd.dea(), "golden_cross");
        Integer macdDeathDays = IndicatorMath.lastCrossAge(macd.dif(), macd.dea(), "death_cross");

        builder.dif(dif);
        builder.dea(dea);
        builder.macdHist(macdHist);
        builder.macdCrossSignal(macdSignal);
        builder.macdGoldenCrossDaysAgo(macdGoldenDays);
        builder.macdDeathCrossDaysAgo(macdDeathDays);
    }
}
