package com.quantization.module.backtest;

import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 回测策略 JPA Repository，提供按创建时间倒序查询全部策略。
 */
@Repository
public interface BacktestStrategyRepository extends JpaRepository<BacktestStrategyEntity, Long> {
    /** 查询全部策略，按创建时间倒序排列。 */
    List<BacktestStrategyEntity> findAllByOrderByCreatedAtDesc();

    /** 按来源过滤策略，按创建时间倒序排列。 */
    List<BacktestStrategyEntity> findBySourceOrderByCreatedAtDesc(String source);

    /** 查询最近 N 次回测记录，按创建时间倒序排列。 */
    default List<BacktestStrategyEntity> findRecentRuns(int limit) {
        int safeLimit = Math.max(1, limit);
        return findAll(PageRequest.of(0, safeLimit, Sort.by(Sort.Direction.DESC, "createdAt"))).getContent();
    }
}
