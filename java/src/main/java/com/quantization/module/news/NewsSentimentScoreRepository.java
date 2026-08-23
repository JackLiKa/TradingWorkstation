package com.quantization.module.news;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 新闻情感评分 Repository — 提供利好池/利空池查询。
 */
@Repository
public interface NewsSentimentScoreRepository extends JpaRepository<NewsSentimentScoreEntity, Long> {

    /** 查询是否存在相同 uri + queryContext 的评分（去重） */
    boolean existsByUriAndQueryContext(String uri, String queryContext);

    /** 利好池：direction >= minDirection 且 sustainability >= minSustainability，最近 N 天 */
    List<NewsSentimentScoreEntity> findByDirectionGreaterThanEqualAndSustainabilityGreaterThanEqualAndScoredAtAfterOrderByCompositeScoreDesc(
            Integer minDirection, Integer minSustainability, LocalDateTime after, Pageable pageable);

    /** 利空池：direction <= -minAbsDirection 且 sustainability >= minSustainability，最近 N 天 */
    List<NewsSentimentScoreEntity> findByDirectionLessThanEqualAndSustainabilityGreaterThanEqualAndScoredAtAfterOrderByCompositeScoreAsc(
            Integer maxDirection, Integer minSustainability, LocalDateTime after, Pageable pageable);

    /** 清理过期评分 */
    long deleteByScoredAtBefore(LocalDateTime before);
}
