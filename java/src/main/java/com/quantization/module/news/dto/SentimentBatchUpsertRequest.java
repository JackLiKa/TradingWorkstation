package com.quantization.module.news.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * 新闻情感评分批量写入请求 — Agent reranker 评分后调用。
 */
public record SentimentBatchUpsertRequest(List<SentimentItemInput> items) {

    public record SentimentItemInput(
            String uri,
            String title,
            Integer direction,
            Integer sustainability,
            BigDecimal compositeScore,
            String newsLabel,
            String queryContext
    ) {}
}
