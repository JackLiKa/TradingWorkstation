package com.quantization.module.news;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 新闻情感评分实体，对应 news_sentiment_score 表。
 * <p>
 * 存储 LLM reranker 的双维度评分结果（direction + sustainability），
 * 用于建立「利好池」「利空池」，策略生成时只从利好池选股。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "news_sentiment_score", uniqueConstraints = @UniqueConstraint(name = "uk_news_sentiment_uri_query", columnNames = {"uri", "queryContext"}))
public class NewsSentimentScoreEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "uri", nullable = false, length = 200)
    private String uri;

    @Column(name = "title", nullable = false, length = 500)
    private String title;

    /** 利好/利空方向：-10 到 +10 */
    @Column(name = "direction", nullable = false)
    private Integer direction;

    /** 持续性评分：0 到 10 */
    @Column(name = "sustainability", nullable = false)
    private Integer sustainability;

    /** 综合分数 = direction * sustainability / 10 */
    @Column(name = "composite_score", nullable = false, precision = 5, scale = 2)
    private BigDecimal compositeScore;

    /** 分类标签：持续性利好/一日遊利好/弱利好/中性/弱利空/持续性利空/一日遊利空 */
    @Column(name = "news_label", nullable = false, length = 20)
    private String newsLabel;

    /** 评分时的查询上下文 */
    @Column(name = "query_context", length = 500)
    private String queryContext;

    @Column(name = "scored_at", nullable = false)
    private LocalDateTime scoredAt;
}
