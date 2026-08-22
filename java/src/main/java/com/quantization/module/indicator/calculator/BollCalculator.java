package com.quantization.module.indicator.calculator;

import com.quantization.module.indicator.IndicatorCalculator;
import com.quantization.module.indicator.IndicatorConfig;
import com.quantization.module.indicator.IndicatorMath;
import com.quantization.module.indicator.IndicatorSnapshotBuilder;
import com.quantization.module.stock.StockDaily;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 布林带（BOLL）指标计算器 — 计算上/中/下轨最新值、带宽、%B 与位置。
 * 逻辑与原 {@code IndicatorEngine.buildSnapshot} 中 BOLL 部分完全一致。
 */
@Component
public class BollCalculator implements IndicatorCalculator {

    @Override
    public String name() {
        return "BOLL";
    }

    @Override
    public void calculate(IndicatorSnapshotBuilder builder, List<StockDaily> history, int index) {
        IndicatorConfig config = builder.config();
        IndicatorMath.BollSeries boll = IndicatorMath.boll(builder.closes(), config.bollPeriod(), config.bollStd());

        Double bollUpper = IndicatorSnapshotBuilder.last(boll.upper());
        Double bollMiddle = IndicatorSnapshotBuilder.last(boll.middle());
        Double bollLower = IndicatorSnapshotBuilder.last(boll.lower());

        IndicatorMath.BollStatus bollStatus = IndicatorMath.bollStatus(
                builder.closePrice(), bollUpper, bollMiddle, bollLower);

        builder.bollUpper(bollUpper);
        builder.bollMiddle(bollMiddle);
        builder.bollLower(bollLower);
        builder.bollWidth(bollStatus.width());
        builder.bollPercentB(bollStatus.percentB());
        builder.bollPosition(bollStatus.position());
    }
}
