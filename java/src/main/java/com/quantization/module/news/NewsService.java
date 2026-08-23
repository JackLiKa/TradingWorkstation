package com.quantization.module.news;

import com.quantization.module.news.dto.FinancialNewsDto;
import com.quantization.module.news.dto.NewsBatchUpsertRequest;
import com.quantization.module.news.dto.NewsSyncResultDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;

/**
 * 财经新闻服务 — 提供新闻查询和过期清理。
 * <p>
 * 新闻抓取由 Agent 服务（wallstreetcn_client.py）负责，
 * 本服务负责 MySQL 持久化层的查询和清理。
 */
@Slf4j
@Service
public class NewsService {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final FinancialNewsRepository repository;

    public NewsService(FinancialNewsRepository repository) {
        this.repository = repository;
    }

    /**
     * 分页查询最新新闻。
     */
    public Page<FinancialNewsDto> listLatest(int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return repository.findAllByOrderByPublishedAtDesc(pageable)
                .map(FinancialNewsDto::from);
    }

    /**
     * 按频道分页查询。
     */
    public Page<FinancialNewsDto> listByChannel(String channel, int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return repository.findByChannelOrderByPublishedAtDesc(channel, pageable)
                .map(FinancialNewsDto::from);
    }

    /**
     * 查询指定时间之后的新闻（供 Agent 服务调用）。
     */
    public List<FinancialNewsDto> listSince(LocalDateTime after) {
        return repository.findByPublishedAtAfterOrderByPublishedAtDesc(after)
                .stream()
                .map(FinancialNewsDto::from)
                .toList();
    }

    /**
     * 清理过期新闻（删除指定天数之前的记录）。
     *
     * @param days 保留天数
     * @return 删除的条数
     */
    @Transactional
    public int cleanupExpired(int days) {
        LocalDateTime cutoff = LocalDateTime.now().minusDays(days);
        long deleted = repository.deleteByPublishedAtBefore(cutoff);
        log.info("[news] 清理过期新闻: 删除 {} 条（{} 之前）", deleted, cutoff.format(TS));
        return (int) deleted;
    }

    /**
     * 获取新闻总数。
     */
    public long count() {
        return repository.count();
    }

    /**
     * 清空所有新闻（重建时调用）。
     */
    @Transactional
    public void deleteAll() {
        repository.deleteAll();
        log.info("[news] 已清空所有新闻");
    }

    /**
     * 批量 upsert 新闻 — Agent 服务抓取后调用。
     * URI 去重：已存在的 URI 跳过。
     *
     * @param items 新闻列表
     * @return 同步结果统计
     */
    @Transactional
    public NewsSyncResultDto batchUpsert(List<NewsBatchUpsertRequest.NewsItemInput> items) {
        if (items == null || items.isEmpty()) {
            return NewsSyncResultDto.success(0, 0, 0, 0);
        }
        int stored = 0;
        int duplicated = 0;
        int failed = 0;
        for (NewsBatchUpsertRequest.NewsItemInput item : items) {
            try {
                String uri = item.uri();
                if (uri == null || uri.isBlank()) {
                    failed++;
                    continue;
                }
                if (repository.existsByUri(uri)) {
                    duplicated++;
                    continue;
                }
                FinancialNewsEntity entity = new FinancialNewsEntity();
                entity.setUri(uri);
                entity.setTitle(item.title() != null ? item.title() : "");
                entity.setSummary(item.summary());
                entity.setContent(item.content());
                entity.setSource(item.source() != null ? item.source() : "華爾街見聞");
                entity.setAuthor(item.author());
                entity.setChannel(item.channel());
                // 解析日期（格式 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD）
                if (item.date() != null && !item.date().isBlank()) {
                    try {
                        entity.setPublishedAt(LocalDateTime.parse(item.date(), TS));
                    } catch (Exception e) {
                        try {
                            entity.setPublishedAt(LocalDateTime.parse(item.date() + " 00:00:00", TS));
                        } catch (Exception ex) {
                            log.debug("[news] 日期解析失敗: {}", item.date());
                        }
                    }
                }
                entity.setUrl(item.url());
                entity.setImageUrl(item.imageUrl());
                entity.setCreatedAt(LocalDateTime.now());
                repository.save(entity);
                stored++;
            } catch (Exception e) {
                log.warn("[news] 新聞入庫失敗: {}", e.getMessage());
                failed++;
            }
        }
        log.info("[news] 批量 upsert: {} 條請求, {} 新存入, {} 重複, {} 失敗",
                items.size(), stored, duplicated, failed);
        return NewsSyncResultDto.success(items.size(), stored, duplicated, failed);
    }
}
