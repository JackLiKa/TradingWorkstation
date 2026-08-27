package com.quantization.module.dailydigest;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 當日市場摘要實體 — 每個交易日一條，同交易日內所有 AI 節點複用。
 * 減少工具調用、提高數據命中率、減小幻覺風險。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "daily_market_digest")
public class DailyDigestEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** 交易日（唯一鍵，每個交易日一條） */
    @Column(name = "trade_date", nullable = false, unique = true)
    private LocalDate tradeDate;

    /** 市場概覽（指數表現、漲跌家數、成交額） */
    @Column(name = "market_overview", columnDefinition = "TEXT", nullable = false)
    private String marketOverview;

    /** 板塊亮點（強勢/弱勢行業） */
    @Column(name = "sector_highlights", columnDefinition = "TEXT", nullable = false)
    private String sectorHighlights;

    /** 新聞摘要（已凝練的關鍵新聞） */
    @Column(name = "news_digest", columnDefinition = "TEXT", nullable = false)
    private String newsDigest;

    /** 市場情緒（偏多/中性/偏空 + 理由） */
    @Column(name = "sentiment", nullable = false, length = 500)
    private String sentiment;

    /** 關鍵事件 JSON 數組 */
    @Column(name = "key_events_json", columnDefinition = "TEXT")
    private String keyEventsJson;

    /** 數據來源 JSON 數組 */
    @Column(name = "data_sources_json", columnDefinition = "TEXT")
    private String dataSourcesJson;

    /** 生成時間 */
    @Column(name = "generated_at", nullable = false)
    private LocalDateTime generatedAt;
}
