package com.quantization.module.indicator.calculator;

import com.quantization.module.indicator.IndicatorCalculator;
import com.quantization.module.indicator.IndicatorMath;
import com.quantization.module.indicator.IndicatorSnapshotBuilder;
import com.quantization.module.stock.StockDaily;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * RSI(14) 计算器。
 * 逻辑与原 {@code IndicatorEngine.buildSnapshot} 中 RSI 部分完全一致。
 */
@Component
public class RsiCalculator implements IndicatorCalculator {

    @Override
    public String name() {
        return "RSI";
    }

    @Override
    public void calculate(IndicatorSnapshotBuilder builder, List<StockDaily> history, int index) {
        builder.rsi14(IndicatorMath.rsi(builder.closes(), 14));
    }
}
