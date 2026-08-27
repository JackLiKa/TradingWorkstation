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
import java.time.LocalDateTime;

/**
 * 股票日线持久化实体，对应 stock_daily 表。
 * 唯一键为 (code, date, adjustflag)，支持三种复权方式的数据共存。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "stock_daily")
public class StockDailyEntity {

    @Id
    @Column(name = "id")
    private Long id;

    @Column(name = "code", nullable = false, length = 20)
    private String code;

    @Column(name = "date", nullable = false)
    private LocalDate tradeDate;

    @Column(name = "open", precision = 20, scale = 4)
    private BigDecimal openPrice;

    @Column(name = "high", precision = 20, scale = 4)
    private BigDecimal highPrice;

    @Column(name = "low", precision = 20, scale = 4)
    private BigDecimal lowPrice;

    @Column(name = "close", precision = 20, scale = 4)
    private BigDecimal closePrice;

    @Column(name = "preclose", precision = 20, scale = 4)
    private BigDecimal preclosePrice;

    @Column(name = "volume")
    private Long volume;

    @Column(name = "amount", precision = 30, scale = 2)
    private BigDecimal amount;

    @Column(name = "adjustflag")
    private Integer adjustflag;

    @Column(name = "turn", precision = 10, scale = 4)
    private BigDecimal turn;

    @Column(name = "tradestatus")
    private Integer tradeStatus;

    @Column(name = "pctChg", precision = 10, scale = 4)
    private BigDecimal pctChange;

    @Column(name = "isST")
    private Integer isSt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
