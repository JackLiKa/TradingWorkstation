package com.quantization.module.stock;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

/**
 * 股票行業分類 Repository。
 */
public interface StockIndustryRepository extends JpaRepository<StockIndustryEntity, Long> {

    /** 根據股票代碼查詢行業信息。 */
    List<StockIndustryEntity> findByCode(String code);

    /** 查詢所有不同的行業分類。 */
    @Query("SELECT DISTINCT s.industry FROM StockIndustryEntity s WHERE s.industry IS NOT NULL AND s.industry <> ''")
    List<String> findDistinctIndustries();

    /** 根據行業關鍵詞模糊查詢股票代碼。 */
    @Query("SELECT s FROM StockIndustryEntity s WHERE s.industry LIKE %:keyword%")
    List<StockIndustryEntity> findByIndustryContaining(@Param("keyword") String keyword);

    /** 查詢所有行業分類記錄（帶分頁）。 */
    List<StockIndustryEntity> findAllByOrderByCodeAsc();
}
