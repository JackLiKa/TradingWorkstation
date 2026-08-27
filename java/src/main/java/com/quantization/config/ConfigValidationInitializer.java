package com.quantization.config;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

/**
 * 啟動時配置校驗：檢查敏感/必填配置項是否已正確設置。
 * <p>
 * 不阻止啟動（單機工作台容許空密碼連本地 MySQL），但打出明確 WARN 日誌，
 * 避免錯配靜默運行到首次連接才炸。
 * </p>
 */
@Component
public class ConfigValidationInitializer {

    private static final Logger log = LoggerFactory.getLogger(ConfigValidationInitializer.class);

    private final Environment env;

    public ConfigValidationInitializer(Environment env) {
        this.env = env;
    }

    @PostConstruct
    public void validate() {
        warnIfBlank("DB_PASSWORD", "數據庫密碼為空，本地開發可接受，生產環境必須設置");
        warnIfBlank("DB_USER", "數據庫用戶名為空，將使用默認值 root");

        // 通知服務啟用時校驗必填子配置
        if (isEnabled("NOTIFICATION_ENABLED")) {
            if (isEnabled("MAIL_ENABLED")) {
                warnIfBlank("MAIL_USERNAME", "郵件通知已啟用但 MAIL_USERNAME 為空");
                warnIfBlank("MAIL_PASSWORD", "郵件通知已啟用但 MAIL_PASSWORD 為空");
                warnIfBlank("MAIL_FROM", "郵件通知已啟用但 MAIL_FROM 為空");
                warnIfBlank("MAIL_TO", "郵件通知已啟用但 MAIL_TO 為空");
            }
            if (isEnabled("WEBHOOK_ENABLED")) {
                warnIfBlank("WEBHOOK_URL", "Webhook 通知已啟用但 WEBHOOK_URL 為空");
                warnIfBlank("WEBHOOK_SECRET", "Webhook 通知已啟用但 WEBHOOK_SECRET 為空，簽名頭將不發送");
            }
        }
    }

    private void warnIfBlank(String key, String message) {
        String value = env.getProperty(key);
        if (value == null || value.isBlank()) {
            log.warn("[config] {} — {}", key, message);
        }
    }

    private boolean isEnabled(String key) {
        String value = env.getProperty(key);
        return "true".equalsIgnoreCase(value);
    }
}
