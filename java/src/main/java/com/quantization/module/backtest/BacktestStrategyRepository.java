package com.quantization.module.backtest;

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
}
