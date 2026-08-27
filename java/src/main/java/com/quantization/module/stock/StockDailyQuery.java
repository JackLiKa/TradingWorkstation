package com.quantization.module.stock;

import java.time.LocalDate;
import java.util.List;

/** 查询参数（与原 StockDailyQuery 对齐）。 */
public record StockDailyQuery(
        String code,
        int adjustflag,
        LocalDate startDate,
        LocalDate endDate,
        int limit,
        int offset
) {
    public static StockDailyQuery empty() {
        return new StockDailyQuery("", 3, null, null, 200, 0);
    }
}
