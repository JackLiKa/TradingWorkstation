package com.quantization.module.sync;

import com.quantization.config.properties.AppProperties;
import com.quantization.module.sync.dto.SyncRequestDto;
import com.quantization.module.sync.dto.SyncStatusDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;

import java.time.LocalDate;

/**
 * 每日自動增量同步排程器 — 啟動時補齊 + 每個交易日收盤後定時增量更新。
 *
 * <p>解決的問題：用戶關機後重啟，數據停留在第 3 天，當前是第 10 天。
 * 啟動時自動執行增量同步，從 MAX(date)+1 拉到今天，完整補齊第 4~10 天的數據。
 * 之後每個交易日收盤後定時執行增量同步，保持數據最新。</p>
 *
 * <p>增量同步邏輯（由 baostock_ingest.py --mode incremental 實現）：
 * <ul>
 *   <li>每隻股票：查 MAX(date) → 從 MAX(date)+1 拉到今天</li>
 *   <li>每個指數：查 MAX(date) → 從 MAX(date)+1 拉到今天</li>
 *   <li>行業分類：每週一更新（Baostock 限制），其餘跳過</li>
 * </ul>
 * 因此無論停機多久，重啟後都能完整補齊缺失的數據。</p>
 *
 * <p>配置項（application.yml / 環境變量）：
 * <ul>
 *   <li>{@code app.sync.daily-enabled} / {@code SYNC_DAILY_ENABLED}：是否啟用（默認 true）</li>
 *   <li>{@code app.sync.daily-cron} / {@code SYNC_DAILY_CRON}：定時同步 cron（默認每週一到五 16:30）</li>
 *   <li>{@code app.sync.catchup-on-startup} / {@code SYNC_CATCHUP_ON_STARTUP}：啟動時是否補齊（默認 true）</li>
 *   <li>{@code app.sync.catchup-delay-seconds} / {@code SYNC_CATCHUP_DELAY_SECONDS}：啟動後延遲多少秒再補齊（默認 30，避免與其他啟動任務衝突）</li>
 * </ul>
 */
@Slf4j
@Configuration
@ConditionalOnProperty(
        name = "app.sync.daily-enabled",
        havingValue = "true",
        matchIfMissing = true
)
public class DailySyncScheduler {

    private final SyncService syncService;
    private final AppProperties properties;

    public DailySyncScheduler(SyncService syncService, AppProperties properties) {
        this.syncService = syncService;
        this.properties = properties;
    }

    /**
     * 啟動時自動補齊缺失數據。
     *
     * <p>在 ApplicationReadyEvent 後延遲執行（默認 30 秒），避免與其他啟動任務衝突。
     * 增量模式會對每隻股票/指數查 MAX(date)，從 MAX(date)+1 拉到今天，
     * 完整補齊停機期間漏掉的所有數據。</p>
     */
    @EventListener(ApplicationReadyEvent.class)
    public void onStartupCatchup() {
        if (!properties.getSync().isCatchupOnStartup()) {
            log.info("啟動時數據補齊已禁用 (sync.catchup-on-startup=false)");
            return;
        }

        int delaySeconds = properties.getSync().getCatchupDelaySeconds();
        log.info("啟動時數據補齊已排程: {} 秒後執行增量同步（補齊停機期間缺失數據）", delaySeconds);

        Thread catchupThread = new Thread(() -> {
            try {
                Thread.sleep(delaySeconds * 1000L);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }
            runIncrementalSync("啟動補齊");
        }, "startup-catchup-sync");
        catchupThread.setDaemon(true);
        catchupThread.start();
    }

    /**
     * 每個交易日收盤後定時增量同步。
     *
     * <p>默認 cron: 0 30 16 * * MON-FRI（每週一到五 16:30，A 股 15:00 收盤後半小時）。
     * 可通過 app.sync.daily-cron 配置。</p>
     */
    @Scheduled(cron = "${app.sync.daily-cron:0 30 16 * * MON-FRI}")
    public void executeDailySync() {
        runIncrementalSync("每日定時");
    }

    /**
     * 執行增量同步：三種復權 + 指數 + 行業。
     *
     * <p>增量模式由 baostock_ingest.py 負責 gap-filling：
     * 每隻股票/指數從 DB 中 MAX(date)+1 拉到今天，確保完整補齊。</p>
     *
     * @param trigger 觸發來源描述（用於日誌）
     */
    private void runIncrementalSync(String trigger) {
        log.info("[{}] 開始執行增量數據同步（三種復權 + 指數 + 行業）", trigger);

        // 檢查是否有任務正在運行
        SyncStatusDto current = syncService.currentStatus();
        if ("RUNNING".equals(current.state())) {
            log.info("[{}] 已有同步任務正在運行，跳過本次（當前狀態: {}）", trigger, current.state());
            return;
        }

        try {
            // 構造增量同步請求：
            // - mode=incremental：每隻股票/指數從 MAX(date)+1 拉到今天
            // - adjustflags=1,2,3：三種復權類型全部更新
            // - syncIndex=true：同步指數
            // - syncIndustry=true：同步行業（Baostock 每週一更新，其餘天跳過）
            // - startDate=null：增量模式由腳本從 DB 查 MAX(date) 決定起始日期
            // - endDate=null：自動用今天
            SyncRequestDto request = new SyncRequestDto(
                    "1,2,3",           // 三種復權
                    null,              // 起始日期由腳本從 DB MAX(date) 決定
                    LocalDate.now(),   // 結束日期 = 今天
                    null,              // 所有股票
                    "incremental",     // 增量模式
                    true,              // 同步指數
                    true               // 同步行業
            );
            SyncStatusDto status = syncService.start(request);
            log.info("[{}] 增量同步已啟動: {}", trigger, status.state());
        } catch (Exception e) {
            log.error("[{}] 增量同步啟動失敗: {}", trigger, e.getMessage(), e);
        }
    }
}
