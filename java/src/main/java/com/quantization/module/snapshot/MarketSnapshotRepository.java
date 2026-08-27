package com.quantization.module.snapshot;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * 行情快照 Repository — 按交易日和快照類型查詢。
 */
@Repository
public interface MarketSnapshotRepository extends JpaRepository<MarketSnapshotEntity, Long> {

    /** 按交易日 + 快照類型查詢 */
    Optional<MarketSnapshotEntity> findByTradeDateAndSnapshotType(LocalDate tradeDate, String snapshotType);

    /** 查詢某交易日的所有快照類型 */
    List<MarketSnapshotEntity> findByTradeDate(LocalDate tradeDate);

    /** 查詢某快照類型的最新 N 條記錄 */
    List<MarketSnapshotEntity> findTop10BySnapshotTypeOrderByTradeDateDesc(String snapshotType);

    /** 查詢最新交易日 */
    Optional<MarketSnapshotEntity> findTopBySnapshotTypeOrderByTradeDateDesc(String snapshotType);
}
