package com.quantization.module.news;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 财经新闻 Repository — 提供 URI 去重查询、频道过滤、时间范围查询。
 */
@Repository
public interface FinancialNewsRepository extends JpaRepository<FinancialNewsEntity, Long> {

    /** 按 URI 查询（去重检查） */
    boolean existsByUri(String uri);

    /** 按频道分页查询（最新的在前） */
    Page<FinancialNewsEntity> findByChannelOrderByPublishedAtDesc(String channel, Pageable pageable);

    /** 查询指定时间之后的新闻（用于增量同步） */
    List<FinancialNewsEntity> findByPublishedAtAfterOrderByPublishedAtDesc(LocalDateTime after);

    /** 全量分页查询（最新的在前） */
    Page<FinancialNewsEntity> findAllByOrderByPublishedAtDesc(Pageable pageable);

    /** 按频道+时间范围查询 */
    List<FinancialNewsEntity> findByChannelAndPublishedAtAfterOrderByPublishedAtDesc(
            String channel, LocalDateTime after);

    /** 清理过期新闻（删除指定时间之前的记录） */
    long deleteByPublishedAtBefore(LocalDateTime before);
}
