package com.quantization.module.stock;

import org.springframework.stereotype.Component;

import java.math.BigDecimal;

/**
 * 实体到领域对象的映射器，将 {@link StockDailyEntity} 转换为 {@link StockDaily}。
 * BigDecimal 字段自动转为 Double，null 保持不变。
 */
@Component
public final class StockDailyMapper {
    private StockDailyMapper() {}

    /**
     * 将持久化实体转换为领域记录。
     *
     * @param e 持久化实体，可为 null
     * @return 领域记录，或 null
     */
    public static StockDaily toDomain(StockDailyEntity e) {
        if (e == null) return null;
        return new StockDaily(
                e.getCode(),
                e.getTradeDate(),
                toDouble(e.getOpenPrice()),
                toDouble(e.getHighPrice()),
                toDouble(e.getLowPrice()),
                toDouble(e.getClosePrice()),
                toDouble(e.getPreclosePrice()),
                e.getVolume(),
                toDouble(e.getAmount()),
                e.getAdjustflag() == null ? 0 : e.getAdjustflag(),
                toDouble(e.getTurn()),
                e.getTradeStatus(),
                toDouble(e.getPctChange()),
                e.getIsSt()
        );
    }

    private static Double toDouble(BigDecimal value) {
        return value == null ? null : value.doubleValue();
    }
}
