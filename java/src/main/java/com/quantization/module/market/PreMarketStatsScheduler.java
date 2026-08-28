package com.quantization.module.market;

import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class PreMarketStatsScheduler {

    private final PreMarketStatsService preMarketStatsService;

    public PreMarketStatsScheduler(PreMarketStatsService preMarketStatsService) {
        this.preMarketStatsService = preMarketStatsService;
    }

    @Scheduled(cron = "0 0 18 * * MON-FRI")
    public void executePreCompute() {
        log.info("[pre-market-scheduler] 開始執行每日預計算任務（18:00）");
        try {
            preMarketStatsService.computeAndSaveDailyStats();
        } catch (Exception e) {
            log.error("[pre-market-scheduler] 預計算任務執行失敗", e);
        }
    }
}
