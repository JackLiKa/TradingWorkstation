package com.quantization.module.news.dto;

import com.quantization.module.news.NewsSentimentScoreEntity;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 新闻情感评分 DTO — 用于 API 响应和 Agent 服务交互。
 */
public record NewsSentimentScoreDto(
        String uri,
        String title,
        Integer direction,
        Integer sustainability,
        BigDecimal compositeScore,
        String newsLabel,
        String queryContext,
        LocalDateTime scoredAt
) {
    public static NewsSentimentScoreDto from(NewsSentimentScoreEntity entity) {
        return new NewsSentimentScoreDto(
                entity.getUri(),
                entity.getTitle(),
                entity.getDirection(),
                entity.getSustainability(),
                entity.getCompositeScore(),
                entity.getNewsLabel(),
                entity.getQueryContext(),
                entity.getScoredAt()
        );
    }
}
