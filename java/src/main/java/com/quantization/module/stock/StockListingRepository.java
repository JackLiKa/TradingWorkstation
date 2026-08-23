package com.quantization.module.stock;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Set;

/**
 * 股票上市狀態 JPA Repository，用於消除倖存者偏差。
 * 查詢指定日期仍在市的股票代碼集合。
 */
@Repository
public interface StockListingRepository extends JpaRepository<StockListingEntity, String> {

    /** 查詢指定日期仍在市的股票代碼（listing_date <= date 且 (delisting_date is null 或 delisting_date > date)）。 */
    @Query("SELECT s.code FROM StockListingEntity s " +
           "WHERE s.listingDate <= :date " +
           "AND (s.delistingDate IS NULL OR s.delistingDate > :date)")
    Set<String> findActiveOnDate(@Param("date") LocalDate date);

    /** 查詢指定日期仍在市的股票代碼（含板塊過濾）。 */
    @Query("SELECT s.code FROM StockListingEntity s " +
           "WHERE s.listingDate <= :date " +
           "AND (s.delistingDate IS NULL OR s.delistingDate > :date) " +
           "AND s.board IN :boards")
    Set<String> findActiveOnDateByBoards(@Param("date") LocalDate date, @Param("boards") List<String> boards);

    /** 根據代碼查詢板塊。 */
    StockListingEntity findByCode(String code);

    /** 根據多個代碼批量查詢。 */
    List<StockListingEntity> findByCodeIn(List<String> codes);
}
