package com.quantization.module.stock;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;

/**
 * 指数日线 JPA Repository，提供按代码和日期区间查询指数数据。
 */
@Repository
public interface IndexDailyRepository extends JpaRepository<IndexDailyEntity, Long> {
    /** 根据指数代码和日期区间查询，按交易日期升序返回。 */
    List<IndexDailyEntity> findByCodeAndTradeDateBetweenOrderByTradeDateAsc(
            String code, LocalDate start, LocalDate end);
}
