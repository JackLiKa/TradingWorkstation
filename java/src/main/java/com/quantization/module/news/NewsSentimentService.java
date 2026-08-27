package com.quantization.module.news;

import com.quantization.module.news.dto.NewsSentimentScoreDto;
import com.quantization.module.news.dto.SentimentBatchUpsertRequest;
import com.quantization.module.news.dto.SentimentSyncResultDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 新闻情感评分服务 — 提供评分持久化、利好池/利空池查询。
 * <p>
 * 评分由 Agent 服务的 LLM reranker 生成，本服务负责 MySQL 持久化。
 * 利好池/利空池用于策略生成时引导选股方向。
 */
@Slf4j
@Service
public class NewsSentimentService {

    private final NewsSentimentScoreRepository repository;

    public NewsSentimentService(NewsSentimentScoreRepository repository) {
        this.repository = repository;
    }

    /**
     * 批量 upsert 情感评分 — Agent reranker 评分后调用。
     * 去重：相同 uri + queryContext 的评分跳过。
     */
    @Transactional
    public SentimentSyncResultDto batchUpsert(List<SentimentBatchUpsertRequest.SentimentItemInput> items) {
        if (items == null || items.isEmpty()) {
            return SentimentSyncResultDto.success(0, 0, 0, 0);
        }
        int stored = 0;
        int duplicated = 0;
        int failed = 0;
        for (SentimentBatchUpsertRequest.SentimentItemInput item : items) {
            try {
                String uri = item.uri();
                if (uri == null || uri.isBlank()) {
                    failed++;
                    continue;
                }
                String ctx = item.queryContext() != null ? item.queryContext() : "";
                if (repository.existsByUriAndQueryContext(uri, ctx)) {
                    duplicated++;
                    continue;
                }
                NewsSentimentScoreEntity entity = new NewsSentimentScoreEntity();
                entity.setUri(uri);
                entity.setTitle(item.title() != null ? item.title() : "");
                entity.setDirection(item.direction() != null ? item.direction() : 0);
                entity.setSustainability(item.sustainability() != null ? item.sustainability() : 0);
                entity.setCompositeScore(item.compositeScore() != null ? item.compositeScore() : BigDecimal.ZERO);
                entity.setNewsLabel(item.newsLabel() != null ? item.newsLabel() : "中性");
                entity.setQueryContext(ctx);
                entity.setScoredAt(LocalDateTime.now());
                repository.save(entity);
                stored++;
            } catch (Exception e) {
                log.warn("[sentiment] 評分入庫失敗: {}", e.getMessage());
                failed++;
            }
        }
        log.info("[sentiment] 批量 upsert: {} 條請求, {} 新存入, {} 重複, {} 失敗",
                items.size(), stored, duplicated, failed);
        return SentimentSyncResultDto.success(items.size(), stored, duplicated, failed);
    }

    /**
     * 查询利好池 — 持续性利好新闻（direction >= minDirection 且 sustainability >= minSustainability）。
     */
    public List<NewsSentimentScoreDto> getBullishPool(int daysBack, int minDirection, int minSustainability, int limit) {
        LocalDateTime cutoff = LocalDateTime.now().minusDays(daysBack);
        return repository.findByDirectionGreaterThanEqualAndSustainabilityGreaterThanEqualAndScoredAtAfterOrderByCompositeScoreDesc(
                minDirection, minSustainability, cutoff, PageRequest.of(0, limit)
        ).stream().map(NewsSentimentScoreDto::from).toList();
    }

    /**
     * 查询利空池 — 持续性利空新闻（direction <= -minAbsDirection 且 sustainability >= minSustainability）。
     */
    public List<NewsSentimentScoreDto> getBearishPool(int daysBack, int minAbsDirection, int minSustainability, int limit) {
        LocalDateTime cutoff = LocalDateTime.now().minusDays(daysBack);
        return repository.findByDirectionLessThanEqualAndSustainabilityGreaterThanEqualAndScoredAtAfterOrderByCompositeScoreAsc(
                -minAbsDirection, minSustainability, cutoff, PageRequest.of(0, limit)
        ).stream().map(NewsSentimentScoreDto::from).toList();
    }

    /**
     * 清理过期评分。
     */
    @Transactional
    public int cleanupExpired(int days) {
        LocalDateTime cutoff = LocalDateTime.now().minusDays(days);
        long deleted = repository.deleteByScoredAtBefore(cutoff);
        log.info("[sentiment] 清理過期評分: 刪除 {} 條（{} 之前）", deleted, cutoff);
        return (int) deleted;
    }
}
