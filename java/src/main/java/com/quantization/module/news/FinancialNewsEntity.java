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

import java.time.LocalDateTime;

/**
 * 财经新闻持久化实体，对应 financial_news 表。
 * <p>
 * 数据来源：华尔街见闻 (wallstreetcn.com) 公开 API。
 * 双层去重：
 * <ul>
 *   <li>URI 去重：唯一约束 (uri) 确保同一文章不会重复入库</li>
 *   <li>标题+摘要去重：唯一约束 (title_summary_hash) 确保标题和摘要都相同的新闻不会重复入库</li>
 * </ul>
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "financial_news", uniqueConstraints = {
        @UniqueConstraint(name = "uk_financial_news_uri", columnNames = "uri"),
        @UniqueConstraint(name = "uk_financial_news_title_summary", columnNames = "title_summary_hash")
})
public class FinancialNewsEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** 文章唯一标识（用于去重，来自 wallstreetcn API 的 uri/id） */
    @Column(name = "uri", nullable = false, length = 200)
    private String uri;

    @Column(name = "title", nullable = false, length = 500)
    private String title;

    @Column(name = "summary", length = 2000)
    private String summary;

    /**
     * 标题+摘要的 SHA-256 哈希值，用于内容级去重。
     * 即使 URI 不同（如文章 vs 快訊、不同頻道），標題和摘要都相同則視為重複。
     */
    @Column(name = "title_summary_hash", nullable = false, length = 64)
    private String titleSummaryHash;

    @Column(name = "content", columnDefinition = "TEXT")
    private String content;

    @Column(name = "source", nullable = false, length = 50)
    private String source;

    @Column(name = "author", length = 100)
    private String author;

    /** 频道：global/a-stock/us-stock/hk-stock/forex/commodity/headline/hot/search */
    @Column(name = "channel", length = 50)
    private String channel;

    /** 发布时间（从 wallstreetcn display_time 解析） */
    @Column(name = "published_at")
    private LocalDateTime publishedAt;

    @Column(name = "url", length = 500)
    private String url;

    @Column(name = "image_url", length = 500)
    private String imageUrl;

    /** 入库时间 */
    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;
}
