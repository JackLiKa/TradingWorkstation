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
 * 指数日线持久化实体，对应 index_daily 表。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "index_daily")
public class IndexDailyEntity {

    @Id
    @Column(name = "id")
    private Long id;

    @Column(name = "code", nullable = false, length = 16)
    private String code;

    @Column(name = "date", nullable = false)
    private LocalDate tradeDate;

    @Column(name = "close", precision = 20, scale = 4)
    private BigDecimal closePrice;

    @Column(name = "pctChg", precision = 12, scale = 6)
    private BigDecimal pctChange;
}
