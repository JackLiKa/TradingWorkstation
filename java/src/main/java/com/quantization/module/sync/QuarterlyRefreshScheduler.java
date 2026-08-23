package com.quantization.module.sync;

import com.quantization.config.properties.AppProperties;
import com.quantization.module.sync.dto.SyncRequestDto;
import com.quantization.module.sync.dto.SyncStatusDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.Scheduled;

/**
 * 季度自動全刷前復權（adjustflag=2）數據調度器。
 *
 * <p>前復權數據在除權除息後會被 Baostock 重新計算歷史價格，
 * 增量模式只拉 MAX(date)+1 不刷新歷史數據，導致歷史價格陳舊。
 * 此調度器每季度自動執行全刷，確保回測用到的歷史價格正確。</p>
 */
@Slf4j
@Configuration
@ConditionalOnProperty(
        name = "app.sync.quarterly-full-refresh-enabled",
        havingValue = "true",
        matchIfMissing = true
)
public class QuarterlyRefreshScheduler {

    private final SyncService syncService;
    private final AppProperties properties;

    public QuarterlyRefreshScheduler(SyncService syncService, AppProperties properties) {
        this.syncService = syncService;
        this.properties = properties;
    }

    /**
     * 每季度自動執行 adjustflag=2 全刷。
     * cron 表達式可通過 app.sync.quarterly-refresh-cron 配置。
     */
    @Scheduled(cron = "${app.sync.quarterly-refresh-cron:0 0 2 1 */3 ?}")
    public void executeQuarterlyRefresh() {
        log.info("季度自動全刷：開始執行 adjustflag=2 全量刷新");
        try {
            // 構造全刷請求：range 模式 + adjustflag=2 + 全日期範圍
            SyncRequestDto request = new SyncRequestDto(
                    "range",
                    java.time.LocalDate.parse(properties.getSync().getDefaultStartDate()),
                    java.time.LocalDate.now(),
                    "2",  // 只刷 adjustflag=2
                    null,  // 所有股票
                    true,  // 同步指數
                    true   // 同步行業
            );
            SyncStatusDto status = syncService.start(request);
            log.info("季度自動全刷已啟動: {}", status.state());
        } catch (Exception e) {
            log.error("季度自動全刷啟動失敗: {}", e.getMessage(), e);
        }
    }
}
