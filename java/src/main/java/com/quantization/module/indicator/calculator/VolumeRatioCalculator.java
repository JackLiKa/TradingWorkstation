package com.quantization.module.indicator.calculator;

import com.quantization.module.indicator.IndicatorCalculator;
import com.quantization.module.indicator.IndicatorMath;
import com.quantization.module.indicator.IndicatorSnapshotBuilder;
import com.quantization.module.stock.StockDaily;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 量比（20 日）计算器。
 * 逻辑与原 {@code IndicatorEngine.buildSnapshot} 中量比部分完全一致。
 */
@Component
public class VolumeRatioCalculator implements IndicatorCalculator {

    @Override
    public String name() {
        return "VOLUME_RATIO";
    }

    @Override
    public void calculate(IndicatorSnapshotBuilder builder, List<StockDaily> history, int index) {
        builder.volumeRatio(IndicatorMath.volumeRatio(history, 20));
    }
}
