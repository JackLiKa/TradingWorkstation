package com.quantization.module.stock;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 行業日度聚合實體，對應 industry_daily 表。
 * 由 ingestion/baostock_ingest.py 通過 JOIN stock_daily × stock_industry 聚合生成。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "industry_daily")
public class IndustryDailyEntity {

    @Id
    @Column(name = "id")
    private Long id;

    @Column(name = "date", nullable = false)
    private LocalDate tradeDate;

    @Column(name = "industry", nullable = false, length = 100)
    private String industry;

    @Column(name = "stock_count", nullable = false)
    private Integer stockCount;

    @Column(name = "avg_pct_chg", precision = 20, scale = 6)
    private BigDecimal avgPctChg;

    @Column(name = "total_amount", precision = 30, scale = 2)
    private BigDecimal totalAmount;

    @Column(name = "total_volume")
    private Long totalVolume;

    @Column(name = "avg_turn", precision = 20, scale = 6)
    private BigDecimal avgTurn;

    @Column(name = "rising_count")
    private Integer risingCount;

    @Column(name = "falling_count")
    private Integer fallingCount;

    @Column(name = "avg_close", precision = 20, scale = 4)
    private BigDecimal avgClose;

    @Column(name = "max_close", precision = 20, scale = 4)
    private BigDecimal maxClose;

    @Column(name = "min_close", precision = 20, scale = 4)
    private BigDecimal minClose;
}
