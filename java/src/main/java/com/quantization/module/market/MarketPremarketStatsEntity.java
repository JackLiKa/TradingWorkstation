package com.quantization.module.market;

import jakarta.persistence.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 市場預計算統計實體 — 存儲每日定時任務預計算的波動排行等指標。
 * 對應 market_premarket_stats 表。
 * 數據由每交易日 18:00 定時任務生成，前台直接讀取預計算結果。
 */
@Entity
@Table(name = "market_premarket_stats", uniqueConstraints = {
        @UniqueConstraint(name = "uk_date_type_key", columnNames = {"trade_date", "stat_type", "stat_key"})
})
public class MarketPremarketStatsEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "trade_date", nullable = false)
    private LocalDate tradeDate;

    @Column(name = "stat_type", nullable = false, length = 32)
    private String statType;

    @Column(name = "stat_key", nullable = false, length = 64)
    private String statKey;

    @Column(name = "stat_value", columnDefinition = "TEXT")
    private String statValue;

    @Column(name = "rank")
    private Integer rank;

    @Column(name = "created_at", updatable = false, insertable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", updatable = false, insertable = false)
    private LocalDateTime updatedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public LocalDate getTradeDate() { return tradeDate; }
    public void setTradeDate(LocalDate tradeDate) { this.tradeDate = tradeDate; }
    public String getStatType() { return statType; }
    public void setStatType(String statType) { this.statType = statType; }
    public String getStatKey() { return statKey; }
    public void setStatKey(String statKey) { this.statKey = statKey; }
    public String getStatValue() { return statValue; }
    public void setStatValue(String statValue) { this.statValue = statValue; }
    public Integer getRank() { return rank; }
    public void setRank(Integer rank) { this.rank = rank; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
