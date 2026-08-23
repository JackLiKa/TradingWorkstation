package com.quantization.module.news.dto;

import com.quantization.module.news.FinancialNewsEntity;

import java.time.LocalDateTime;

/**
 * 财经新闻 DTO — 用于 API 响应和 Agent 服务消费。
 */
public record FinancialNewsDto(
        Long id,
        String uri,
        String title,
        String summary,
        String source,
        String author,
        String channel,
        LocalDateTime publishedAt,
        String url,
        String imageUrl
) {
    /**
     * 从实体转换为 DTO。
     */
    public static FinancialNewsDto from(FinancialNewsEntity entity) {
        return new FinancialNewsDto(
                entity.getId(),
                entity.getUri(),
                entity.getTitle(),
                entity.getSummary(),
                entity.getSource(),
                entity.getAuthor(),
                entity.getChannel(),
                entity.getPublishedAt(),
                entity.getUrl(),
                entity.getImageUrl()
        );
    }
}
