package com.quantization.module.news.dto;

import java.util.List;

/**
 * 批量写入新闻请求 DTO — Agent 服务抓取新闻后调用此接口写入 MySQL。
 */
public record NewsBatchUpsertRequest(
        List<NewsItemInput> items
) {
    /**
     * 单条新闻输入。
     */
    public record NewsItemInput(
            String uri,
            String title,
            String summary,
            String content,
            String source,
            String author,
            String channel,
            String date,
            String url,
            String imageUrl
    ) {}
}
