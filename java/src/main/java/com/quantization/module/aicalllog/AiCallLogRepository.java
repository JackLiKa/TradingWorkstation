package com.quantization.module.aicalllog;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * AI 調用日誌 Repository — 提供分頁查詢、按迭代/階段過濾、評分趨勢聚合。
 */
@Repository
public interface AiCallLogRepository extends JpaRepository<AiCallLogEntity, Long> {

    /** 按迭代輪次查詢，按階段順序排列 */
    List<AiCallLogEntity> findByIterationOrderByStageNameAsc(Integer iteration);

    /** 分頁查詢全部，按創建時間倒序 */
    Page<AiCallLogEntity> findAllByOrderByCreatedAtDesc(Pageable pageable);

    /** 按階段名稱分頁查詢 */
    Page<AiCallLogEntity> findByStageNameOrderByCreatedAtDesc(String stageName, Pageable pageable);

    /** 查詢最近 N 條記錄 */
    List<AiCallLogEntity> findTopNByOrderByCreatedAtDesc(Pageable pageable);

    /** 評分趨勢：按迭代聚合各階段的平均評分 */
    @Query("SELECT e.iteration, e.stageName, AVG(e.judgeScore), MAX(e.judgeScore), MIN(e.judgeScore) " +
           "FROM AiCallLogEntity e " +
           "WHERE e.judgeScore IS NOT NULL " +
           "GROUP BY e.iteration, e.stageName " +
           "ORDER BY e.iteration ASC, e.stageName ASC")
    List<Object[]> scoreTrendByIteration();

    /** 按迭代查詢評分摘要 */
    @Query("SELECT e.iteration, AVG(e.judgeScore), COUNT(e.id) " +
           "FROM AiCallLogEntity e " +
           "WHERE e.judgeScore IS NOT NULL " +
           "GROUP BY e.iteration " +
           "ORDER BY e.iteration ASC")
    List<Object[]> iterationScoreSummary();

    /** 查詢所有不同階段名稱 */
    @Query("SELECT DISTINCT e.stageName FROM AiCallLogEntity e ORDER BY e.stageName")
    List<String> findDistinctStageNames();

    /** 查詢最大迭代輪次 */
    @Query("SELECT MAX(e.iteration) FROM AiCallLogEntity e")
    Integer findMaxIteration();

    /** 刪除創建時間早於指定時間點的日誌記錄（清理調度器使用）。 */
    @Modifying
    @Query("DELETE FROM AiCallLogEntity e WHERE e.createdAt < :cutoff")
    int deleteByCreatedAtBefore(@Param("cutoff") LocalDateTime cutoff);
}
