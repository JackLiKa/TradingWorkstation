package com.quantization.module.market;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import java.time.LocalDate;
import java.util.List;

@Repository
public interface MarketPremarketStatsRepository extends JpaRepository<MarketPremarketStatsEntity, Long> {

    List<MarketPremarketStatsEntity> findByTradeDateAndStatTypeOrderByRankAsc(LocalDate tradeDate, String statType);

    @Modifying
    @Query("DELETE FROM MarketPremarketStatsEntity e WHERE e.tradeDate = :date AND e.statType = :type")
    void deleteByDateAndType(@Param("date") LocalDate date, @Param("type") String statType);
}
