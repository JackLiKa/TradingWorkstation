package com.quantization.module.stock.dto;

import java.util.List;

/**
 * 分页搜索结果（含 hasMore 标志，避免昂贵的 COUNT 查询）。
 * 前端可用 offset + limit 做"加载更多"分页。
 */
public record SearchResultDto(
        List<StockDailyDto> items,
        int offset,
        int limit,
        boolean hasMore
) {
    /**
     * 从完整列表构造：传入 limit+1 条记录，自动截断并设置 hasMore。
     */
    public static SearchResultDto of(List<StockDailyDto> records, int offset, int limit) {
        boolean hasMore = records.size() > limit;
        List<StockDailyDto> items = hasMore ? records.subList(0, limit) : records;
        return new SearchResultDto(items, offset, limit, hasMore);
    }
}
