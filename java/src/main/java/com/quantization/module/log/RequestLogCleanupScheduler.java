package com.quantization.module.log;

import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * 請求日誌清理調度器 — 每日凌晨 3:00 自動清理超過 30 天的請求日誌。
 * 實現滑動窗口：只保留最近 1 個月的數據。
 */
@Slf4j
@Component
public class RequestLogCleanupScheduler {

    private final RequestLogRepository requestLogRepository;

    public RequestLogCleanupScheduler(RequestLogRepository requestLogRepository) {
        this.requestLogRepository = requestLogRepository;
    }

    /** 每日凌晨 3:00 清理 30 天前的請求日誌 */
    @Scheduled(cron = "0 0 3 * * *")
    public void cleanupOldLogs() {
        LocalDateTime cutoff = LocalDateTime.now().minusDays(30);
        try {
            int deleted = requestLogRepository.deleteByCreatedAtBefore(cutoff);
            if (deleted > 0) {
                log.info("[log-cleanup] 清理 {} 條過期請求日誌（30天前）", deleted);
            }
        } catch (Exception e) {
            log.error("[log-cleanup] 清理請求日誌失敗", e);
        }
    }
}
