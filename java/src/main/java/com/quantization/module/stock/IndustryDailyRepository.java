package com.quantization.module.stock;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;

/**
 * 行業日度聚合 JPA Repository。
 */
@Repository
public interface IndustryDailyRepository extends JpaRepository<IndustryDailyEntity, Long> {

    /** 根據交易日期查詢全部行業聚合，按平均漲跌幅倒序。 */
    List<IndustryDailyEntity> findByTradeDateOrderByAvgPctChgDesc(LocalDate tradeDate);

    /** 根據交易日期區間和行業名稱查詢，按日期升序。 */
    List<IndustryDailyEntity> findByIndustryAndTradeDateBetweenOrderByTradeDateAsc(
            String industry, LocalDate start, LocalDate end);

    /** 根據交易日期區間查詢全部行業聚合，按日期升序。 */
    List<IndustryDailyEntity> findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(
            LocalDate start, LocalDate end);

    /** 查詢最新交易日。 */
    IndustryDailyEntity findFirstByOrderByTradeDateDesc();
}
