package com.quantization.module.news.dto;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 游标分页结果 — 用于基于 published_at 游标的新闻分页查询。
 *
 * @param items      当前页新闻列表
 * @param nextCursor 下一页游标（最后一条新闻的 publishedAt），无更多数据时为 null
 * @param hasMore    是否还有更多数据
 */
public record CursorPageResult<T>(
        List<T> items,
        LocalDateTime nextCursor,
        boolean hasMore
) {
}
