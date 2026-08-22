package com.quantization.module.system;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 通知服務 — 支援郵件與 Webhook 推送。
 *
 * 配置項（application.yml -> app.notification）：
 * - app.notification.enabled：總開關
 * - app.notification.mail.enabled：郵件開關
 * - app.notification.mail.host/port/username/password/from/to
 * - app.notification.webhook.enabled：Webhook 開關
 * - app.notification.webhook.url/secret
 *
 * 所有推送方法均為異步（@Async），不阻塞調用方。
 */
@Service
public class NotificationService {

    private static final Logger log = LoggerFactory.getLogger(NotificationService.class);

    @Value("${app.notification.enabled:false}")
    private boolean enabled;

    @Value("${app.notification.mail.enabled:false}")
    private boolean mailEnabled;

    @Value("${app.notification.mail.host:smtp.qq.com}")
    private String mailHost;

    @Value("${app.notification.mail.port:465}")
    private int mailPort;

    @Value("${app.notification.mail.username:}")
    private String mailUsername;

    @Value("${app.notification.mail.password:}")
    private String mailPassword;

    @Value("${app.notification.mail.from:}")
    private String mailFrom;

    @Value("${app.notification.mail.to:}")
    private String mailTo;

    @Value("${app.notification.webhook.enabled:false}")
    private boolean webhookEnabled;

    @Value("${app.notification.webhook.url:}")
    private String webhookUrl;

    @Value("${app.notification.webhook.secret:}")
    private String webhookSecret;

    private JavaMailSender mailSender;
    private RestTemplate restTemplate;

    @PostConstruct
    public void init() {
        if (mailEnabled && mailUsername != null && !mailUsername.isEmpty()) {
            org.springframework.mail.javamail.JavaMailSenderImpl impl =
                    new org.springframework.mail.javamail.JavaMailSenderImpl();
            impl.setHost(mailHost);
            impl.setPort(mailPort);
            impl.setUsername(mailUsername);
            impl.setPassword(mailPassword);
            impl.setDefaultEncoding("UTF-8");

            java.util.Properties props = impl.getJavaMailProperties();
            props.put("mail.transport.protocol", "smtp");
            props.put("mail.smtp.auth", "true");
            props.put("mail.smtp.starttls.enable", "true");
            props.put("mail.smtp.ssl.enable", String.valueOf(mailPort == 465));
            props.put("mail.debug", "false");

            this.mailSender = impl;
            log.info("郵件通知已啟用: {}:{}, 發件人: {}", mailHost, mailPort, mailFrom);
        }

        if (webhookEnabled) {
            this.restTemplate = new RestTemplate();
            log.info("Webhook 通知已啟用: {}", webhookUrl);
        }

        if (!enabled) {
            log.info("通知服務未啟用 (app.notification.enabled=false)");
        }
    }

    /**
     * 發送景氣度異常預警通知（異步）。
     *
     * @param analysisDate 分析日期
     * @param summary      摘要
     * @param alerts       預警列表（每條含 industry, alertType, alertTypeName, message 等）
     */
    @Async("notificationExecutor")
    public void sendProsperityAlertNotification(
            String analysisDate, String summary, List<Map<String, Object>> alerts) {
        if (!enabled || alerts == null || alerts.isEmpty()) {
            return;
        }

        String subject = String.format("【景氣度預警】%s — %d 條異常", analysisDate, alerts.size());

        StringBuilder body = new StringBuilder();
        body.append("行業景氣度異常預警報告\n");
        body.append("========================================\n\n");
        body.append("分析日期: ").append(analysisDate).append("\n");
        body.append(summary).append("\n\n");
        body.append("預警明細:\n");
        body.append("----------------------------------------\n");

        for (int i = 0; i < alerts.size(); i++) {
            Map<String, Object> alert = alerts.get(i);
            body.append(String.format("%d. [%s] %s\n", i + 1,
                    alert.getOrDefault("severity", ""),
                    alert.getOrDefault("industry", "")));
            body.append(String.format("   類型: %s\n", alert.getOrDefault("alertTypeName", "")));
            body.append(String.format("   訊息: %s\n", alert.getOrDefault("message", "")));
            body.append(String.format("   景氣度: %.1f -> %.1f (變化 %+.1f)\n",
                    toDouble(alert.get("yesterdayProsperity")),
                    toDouble(alert.get("todayProsperity")),
                    toDouble(alert.get("change"))));
            body.append(String.format("   等級: %s -> %s\n\n",
                    alert.getOrDefault("yesterdayGrade", ""),
                    alert.getOrDefault("todayGrade", "")));
        }

        body.append("\n--\n量化交易工作台 自動通知");

        // 發送郵件
        if (mailEnabled && mailSender != null
                && mailFrom != null && !mailFrom.isEmpty()
                && mailTo != null && !mailTo.isEmpty()) {
            try {
                SimpleMailMessage message = new SimpleMailMessage();
                message.setFrom(mailFrom);
                message.setTo(mailTo.split(","));
                message.setSubject(subject);
                message.setText(body.toString());
                mailSender.send(message);
                log.info("景氣度預警郵件已發送至 {}", mailTo);
            } catch (Exception e) {
                log.warn("景氣度預警郵件發送失敗: {}", e.getMessage());
            }
        }

        // 發送 Webhook（HMAC-SHA256 簽名 + 最多 3 次重試）
        if (webhookEnabled && webhookUrl != null && !webhookUrl.isEmpty()) {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("event", "prosperity_alert");
            payload.put("analysisDate", analysisDate);
            payload.put("summary", summary);
            payload.put("alertCount", alerts.size());
            payload.put("alerts", alerts);

            try {
                String json = new com.fasterxml.jackson.databind.ObjectMapper()
                        .writeValueAsString(payload);
                sendWebhookWithRetry(json, 3);
            } catch (Exception e) {
                log.warn("景氣度預警 Webhook 序列化失敗: {}", e.getMessage());
            }
        }
    }

    /**
     * 測試通知（用於驗證配置是否正確）。
     *
     * @return 通知服務狀態與測試結果
     */
    public String testNotification() {
        StringBuilder result = new StringBuilder();

        result.append("通知服務狀態:\n");
        result.append(String.format("- 總開關: %s\n", enabled ? "啟用" : "禁用"));
        result.append(String.format("- 郵件: %s\n", mailEnabled ? "啟用" : "禁用"));
        if (mailEnabled) {
            result.append(String.format("  - SMTP: %s:%d\n", mailHost, mailPort));
            result.append(String.format("  - 發件人: %s\n", mailFrom.isEmpty() ? "未配置" : mailFrom));
            result.append(String.format("  - 收件人: %s\n", mailTo.isEmpty() ? "未配置" : mailTo));
            result.append(String.format("  - MailSender: %s\n", mailSender != null ? "已初始化" : "未初始化"));
        }
        result.append(String.format("- Webhook: %s\n", webhookEnabled ? "啟用" : "禁用"));
        if (webhookEnabled) {
            result.append(String.format("  - URL: %s\n", webhookUrl.isEmpty() ? "未配置" : webhookUrl));
        }

        // 發送測試通知
        if (enabled) {
            try {
                Map<String, Object> testAlert = new LinkedHashMap<>();
                testAlert.put("industry", "測試行業");
                testAlert.put("alertType", "surge");
                testAlert.put("alertTypeName", "測試預警");
                testAlert.put("severity", "low");
                testAlert.put("message", "這是一條測試預警，用於驗證通知配置。");
                testAlert.put("yesterdayProsperity", 50.0);
                testAlert.put("todayProsperity", 65.0);
                testAlert.put("change", 15.0);
                testAlert.put("yesterdayGrade", "平穩");
                testAlert.put("todayGrade", "景氣");

                sendProsperityAlertNotification("TEST", "測試通知", List.of(testAlert));
                result.append("\n測試通知已觸發（異步發送）。\n");
            } catch (Exception e) {
                result.append(String.format("\n測試通知觸發失敗: %s\n", e.getMessage()));
            }
        }

        return result.toString();
    }

    private static double toDouble(Object obj) {
        if (obj == null) return 0.0;
        if (obj instanceof Number) return ((Number) obj).doubleValue();
        try {
            return Double.parseDouble(obj.toString());
        } catch (Exception e) {
            return 0.0;
        }
    }

    /**
     * 以 HMAC-SHA256 簽名發送 Webhook，失敗時指數退避重試。
     *
     * @param jsonBody    JSON 請求體
     * @param maxAttempts 最大嘗試次數
     */
    private void sendWebhookWithRetry(String jsonBody, int maxAttempts) {
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                HttpHeaders headers = new HttpHeaders();
                headers.setContentType(MediaType.APPLICATION_JSON);
                // HMAC-SHA256 簽名頭，取代將 secret 放入 payload body
                if (webhookSecret != null && !webhookSecret.isEmpty()) {
                    String signature = hmacSha256(webhookSecret, jsonBody);
                    headers.set("X-Webhook-Signature", signature);
                }

                HttpEntity<String> request = new HttpEntity<>(jsonBody, headers);
                ResponseEntity<String> response = restTemplate.postForEntity(webhookUrl, request, String.class);
                log.info("景氣度預警 Webhook 已發送 (attempt {}/{}), 響應: {}", attempt, maxAttempts, response.getStatusCode());
                return;
            } catch (Exception e) {
                log.warn("景氣度預警 Webhook 發送失敗 (attempt {}/{}): {}", attempt, maxAttempts, e.getMessage());
                if (attempt < maxAttempts) {
                    try {
                        Thread.sleep(1000L * attempt);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        return;
                    }
                }
            }
        }
        log.error("景氣度預警 Webhook 發送失敗，已重試 {} 次", maxAttempts);
    }

    /** 計算 HMAC-SHA256 並返回十六進制簽名。 */
    private static String hmacSha256(String secret, String data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            SecretKeySpec keySpec = new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
            mac.init(keySpec);
            byte[] hmac = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hmac);
        } catch (Exception e) {
            throw new RuntimeException("HMAC-SHA256 計算失敗", e);
        }
    }
}
