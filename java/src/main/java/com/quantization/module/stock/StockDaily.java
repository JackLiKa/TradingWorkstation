package com.quantization.module.stock;

import java.time.LocalDate;

/**
 * 行情领域记录（与持久化实体解耦，供指标引擎与业务服务使用）。
 * 与原 Python StockDailyRecord 字段一一对应。
 */
public record StockDaily(
        String code,
        LocalDate tradeDate,
        Double openPrice,
        Double highPrice,
        Double lowPrice,
        Double closePrice,
        Double preclosePrice,
        Long volume,
        Double amount,
        int adjustflag,
        Double turn,
        Integer tradeStatus,
        Double pctChange,
        Integer isSt
) {
    public boolean isStStock() {
        return isSt != null && isSt == 1;
    }
}
