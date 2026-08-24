package com.quantization.module.dailydigest;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * 當日市場摘要 Repository — 按交易日查詢。
 */
@Repository
public interface DailyDigestRepository extends JpaRepository<DailyDigestEntity, Long> {

    /** 按交易日查詢（唯一鍵） */
    Optional<DailyDigestEntity> findByTradeDate(LocalDate tradeDate);

    /** 查詢最近 N 條摘要（按交易日倒序） */
    List<DailyDigestEntity> findTopNByOrderByTradeDateDesc(org.springframework.data.domain.Pageable pageable);
}
