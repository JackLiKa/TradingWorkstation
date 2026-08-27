package com.quantization.module.aicalllog;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * AI 調用日誌清理調度器 — 定時刪除超過保留天數的 {@code ai_call_log} 記錄，控制表容量。
 *
 * 預設關閉，需配置 {@code app.aicalllog.cleanup.enabled=true} 啟用。
 *
 * 配置項：
 * - app.aicalllog.cleanup.enabled：是否啟用定時清理（預設 false）
 * - app.aicalllog.retention-days：日誌保留天數（預設 90）
 * - app.aicalllog.cleanup.cron：Cron 表達式（預設每天凌晨 2:00 執行）
 */
@Component
@ConditionalOnProperty(
        prefix = "app.aicalllog.cleanup",
        name = "enabled",
        havingValue = "true"
)
public class AiCallLogCleanupScheduler {

    private static final Logger log = LoggerFactory.getLogger(AiCallLogCleanupScheduler.class);

    private final AiCallLogRepository repository;

    @Value("${app.aicalllog.retention-days:90}")
    private int retentionDays;

    public AiCallLogCleanupScheduler(AiCallLogRepository repository) {
        this.repository = repository;
        log.info("AI 調用日誌清理調度器已啟用（保留天數={}）", retentionDays);
    }

    /**
     * 每天凌晨 2:00（CST）定時清理過期 AI 調用日誌。
     * Cron：秒 分 時 日 月 週。預設 "0 0 2 * * *"。
     */
    @Scheduled(cron = "${app.aicalllog.cleanup.cron:0 0 2 * * *}")
    @Transactional
    public void cleanup() {
        LocalDateTime cutoff = LocalDateTime.now().minusDays(retentionDays);
        log.info("AI 調用日誌清理開始：刪除 {} 之前的記錄（保留天數={}）", cutoff, retentionDays);
        try {
            int deleted = repository.deleteByCreatedAtBefore(cutoff);
            log.info("AI 調用日誌清理完成：已刪除 {} 條過期記錄", deleted);
        } catch (Exception e) {
            log.error("AI 調用日誌清理失敗", e);
        }
    }

    /** 暴露保留天數配置（供測試驗證）。 */
    public int getRetentionDays() {
        return retentionDays;
    }
}
