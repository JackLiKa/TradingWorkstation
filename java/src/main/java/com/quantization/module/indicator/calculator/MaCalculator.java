package com.quantization.module.indicator.calculator;

import com.quantization.module.indicator.IndicatorCalculator;
import com.quantization.module.indicator.IndicatorMath;
import com.quantization.module.indicator.IndicatorSnapshotBuilder;
import com.quantization.module.stock.StockDaily;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 移动平均线（MA5/MA10/MA20/MA60/MA120）计算器。
 * 逻辑与原 {@code IndicatorEngine.buildSnapshot} 中 MA 部分完全一致。
 */
@Component
public class MaCalculator implements IndicatorCalculator {

    @Override
    public String name() {
        return "MA";
    }

    @Override
    public void calculate(IndicatorSnapshotBuilder builder, List<StockDaily> history, int index) {
        List<Double> closes = builder.closes();
        builder.ma5(IndicatorMath.movingAverage(closes, 5));
        builder.ma10(IndicatorMath.movingAverage(closes, 10));
        builder.ma20(IndicatorMath.movingAverage(closes, 20));
        builder.ma60(IndicatorMath.movingAverage(closes, 60));
        builder.ma120(IndicatorMath.movingAverage(closes, 120));
    }
}
