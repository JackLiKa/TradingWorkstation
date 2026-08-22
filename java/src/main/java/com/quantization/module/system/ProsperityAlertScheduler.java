package com.quantization.module.system;

import com.quantization.module.industry.IndustryService;
import com.quantization.module.stock.dto.ProsperityAlertDto;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 景氣度預警定時調度器 — 解決 P4-8「預警無調度器、僅查詢觸發」問題。
 *
 * 定時檢查行業景氣度異常，發現突變/等級躍遷時自動推送通知。
 * 預設關閉，需配置 app.notification.alert-scheduler.enabled=true 啟用。
 *
 * 配置項：
 * - app.notification.alert-scheduler.enabled：是否啟用定時預警（預設 false）
 * - app.notification.alert-scheduler.threshold：預警閾值（預設 15.0）
 * - app.notification.alert-scheduler.cron：Cron 表達式（預設每交易日 15:30 執行）
 */
@Component
@ConditionalOnProperty(
        prefix = "app.notification.alert-scheduler",
        name = "enabled",
        havingValue = "true"
)
public class ProsperityAlertScheduler {

    private static final Logger log = LoggerFactory.getLogger(ProsperityAlertScheduler.class);

    private final IndustryService industryService;
    private final NotificationService notificationService;

    @Value("${app.notification.alert-scheduler.threshold:15.0}")
    private double threshold;

    public ProsperityAlertScheduler(IndustryService industryService,
                                    NotificationService notificationService) {
        this.industryService = industryService;
        this.notificationService = notificationService;
        log.info("景氣度預警定時調度器已啟用（閾值={}）", threshold);
    }

    /**
     * 每交易日 15:30（CST）定時檢查景氣度異常並推送通知。
     * Cron：秒 分 時 日 月 週。預設 "0 30 15 * * MON-FRI"。
     */
    @Scheduled(cron = "${app.notification.alert-scheduler.cron:0 30 15 * * MON-FRI}")
    public void scheduledAlertCheck() {
        log.info("定時景氣度預警檢查開始");
        try {
            ProsperityAlertDto result = industryService.prosperityAlerts(threshold);
            if (result.alerts() == null || result.alerts().isEmpty()) {
                log.info("定時景氣度預警：無異常（{}）", result.summary());
                return;
            }

            // 轉換為 NotificationService 所需的 List<Map> 格式
            List<Map<String, Object>> alertMaps = new ArrayList<>();
            for (ProsperityAlertDto.AlertEntry entry : result.alerts()) {
                Map<String, Object> map = new HashMap<>();
                map.put("industry", entry.industry());
                map.put("alertType", entry.alertType());
                map.put("alertTypeName", entry.alertTypeName());
                map.put("severity", entry.severity());
                map.put("message", entry.message());
                map.put("yesterdayGrade", entry.yesterdayGrade());
                map.put("todayGrade", entry.todayGrade());
                alertMaps.add(map);
            }

            notificationService.sendProsperityAlertNotification(
                    result.analysisDate(), result.summary(), alertMaps);
            log.info("定時景氣度預警：發現 {} 條異常，已推送通知", result.alerts().size());
        } catch (Exception e) {
            log.error("定時景氣度預警檢查失敗", e);
        }
    }
}
