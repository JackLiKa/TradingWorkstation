package com.quantization.module.stock;

import jakarta.persistence.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 股票上市狀態實體：記錄板塊、上市日期、退市日期，用於消除倖存者偏差。
 */
@Entity
@Table(name = "stock_listing")
public class StockListingEntity {

    @Id
    @Column(name = "code", nullable = false, length = 20)
    private String code;

    @Column(name = "code_name", length = 50)
    private String codeName;

    @Column(name = "board", nullable = false, length = 10)
    private String board;

    @Column(name = "listing_date")
    private LocalDate listingDate;

    @Column(name = "delisting_date")
    private LocalDate delistingDate;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    public StockListingEntity() {}

    public StockListingEntity(String code, String codeName, String board,
                              LocalDate listingDate, LocalDate delistingDate) {
        this.code = code;
        this.codeName = codeName;
        this.board = board;
        this.listingDate = listingDate;
        this.delistingDate = delistingDate;
        this.updatedAt = LocalDateTime.now();
    }

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public String getCodeName() { return codeName; }
    public void setCodeName(String codeName) { this.codeName = codeName; }

    public String getBoard() { return board; }
    public void setBoard(String board) { this.board = board; }

    public LocalDate getListingDate() { return listingDate; }
    public void setListingDate(LocalDate listingDate) { this.listingDate = listingDate; }

    public LocalDate getDelistingDate() { return delistingDate; }
    public void setDelistingDate(LocalDate delistingDate) { this.delistingDate = delistingDate; }

    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
