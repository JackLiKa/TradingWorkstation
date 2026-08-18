package com.quantization.module.stock.dto;

import com.quantization.module.stock.StockDailyQuery;

import java.time.LocalDate;

/**
 * 日线查询参数 DTO（前端传入），字段可为 null，转换为领域查询对象时自动填充默认值。
 */
public record StockDailyQueryDto(
        String code,
        Integer adjustflag,
        LocalDate startDate,
        LocalDate endDate,
        Integer limit,
        Integer offset
) {
    /**
     * 转换为领域查询对象，null 字段填充默认值（adjustflag=3, limit=200, offset=0）。
     *
     * @return 领域查询对象
     */
    public StockDailyQuery toDomain() {
        return new StockDailyQuery(
                code == null ? "" : code,
                adjustflag == null ? 3 : adjustflag,
                startDate,
                endDate,
                limit == null ? 200 : limit,
                offset == null ? 0 : offset
        );
    }
}
