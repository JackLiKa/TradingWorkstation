package com.quantization.module.stock;

import com.quantization.module.stock.dto.StockCodeNameDto;
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

    /**
     * 查詢指定股票代碼的最新行業分類。
     * 對每個 code 取 update_date 最大的那一筆。
     */
    @Query("""
            SELECT s1.code, s1.industry
            FROM StockIndustryEntity s1
            WHERE s1.updateDate = (
                SELECT MAX(s2.updateDate) FROM StockIndustryEntity s2 WHERE s2.code = s1.code
            )
            AND s1.code IN :codes
            """)
    List<Object[]> findLatestIndustriesByCode(@Param("codes") List<String> codes);

    /**
     * 投影查詢：根據行業分類代碼查詢股票 code+name（輕量，不加載完整實體）。
     * 行業代碼如 C38 嵌在 industry 字段中（如「C38電氣機械和器材製造業」），
     * 使用 LIKE 匹配前綴。
     */
    @Query("""
            SELECT DISTINCT new com.quantization.module.stock.dto.StockCodeNameDto(s.code, s.codeName)
            FROM StockIndustryEntity s
            WHERE (s.industry LIKE CONCAT(:prefix1, '%')
            OR s.industry LIKE CONCAT(:prefix2, '%')
            OR s.industry LIKE CONCAT(:prefix3, '%')
            OR s.industry LIKE CONCAT(:prefix4, '%')
            OR s.industry LIKE CONCAT(:prefix5, '%'))
            AND s.codeName IS NOT NULL AND s.codeName <> ''
            ORDER BY s.code
            """)
    List<StockCodeNameDto> findCodeNameByIndustryClassification(
            @Param("prefix1") String prefix1,
            @Param("prefix2") String prefix2,
            @Param("prefix3") String prefix3,
            @Param("prefix4") String prefix4,
            @Param("prefix5") String prefix5);

    /**
     * 投影查詢：根據行業名稱關鍵詞查詢股票 code+name。
     */
    @Query("""
            SELECT DISTINCT new com.quantization.module.stock.dto.StockCodeNameDto(s.code, s.codeName)
            FROM StockIndustryEntity s
            WHERE s.industry LIKE %:keyword%
            AND s.codeName IS NOT NULL AND s.codeName <> ''
            ORDER BY s.code
            """)
    List<StockCodeNameDto> findCodeNameByIndustryContaining(@Param("keyword") String keyword);
}
