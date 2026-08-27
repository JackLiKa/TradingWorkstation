package com.quantization.module.indicator.calculator;

import com.quantization.module.indicator.IndicatorCalculator;
import com.quantization.module.indicator.IndicatorMath;
import com.quantization.module.indicator.IndicatorSnapshotBuilder;
import com.quantization.module.stock.StockDaily;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * N 日区间收益（20/60/120 日）计算器。
 * 逻辑与原 {@code IndicatorEngine.buildSnapshot} 中 return 部分完全一致。
 */
@Component
public class ReturnCalculator implements IndicatorCalculator {

    @Override
    public String name() {
        return "RETURN";
    }

    @Override
    public void calculate(IndicatorSnapshotBuilder builder, List<StockDaily> history, int index) {
        List<Double> closes = builder.closes();
        builder.return20(IndicatorMath.periodReturn(closes, 20));
        builder.return60(IndicatorMath.periodReturn(closes, 60));
        builder.return120(IndicatorMath.periodReturn(closes, 120));
    }
}
