package com.quantization.module.log;

import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.AppenderBase;
import com.quantization.module.log.dto.LogEntry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Logback 內存 Appender — 將 Java 後端應用日誌推入 LogMemoryStore，
 * 供日誌頁面實時展示和 SSE 推送。
 *
 * 註冊方式：在 logback-spring.xml 中添加 <appender-ref ref="MEMORY" />
 * 並通過 logback-spring.xml 的 <bean> 或 Spring Boot 的 logback 配置注入。
 * 此處用 @Component 讓 Spring 管理 Bean，logback-spring.xml 通過 Spring Boot 的
 * logback-spring.xml <springProperty> 或編程式注入。
 *
 * 簡化方案：在構造時通過代碼直接附加到 root logger。
 */
@Slf4j
@Component
public class LogbackInMemoryAppender extends AppenderBase<ILoggingEvent> {

    private final LogMemoryStore logMemoryStore;

    public LogbackInMemoryAppender(LogMemoryStore logMemoryStore) {
        this.logMemoryStore = logMemoryStore;
        setName("MEMORY");
        start();
        // 附加到 root logger
        ch.qos.logback.classic.Logger rootLogger =
                (ch.qos.logback.classic.Logger) org.slf4j.LoggerFactory.getLogger(org.slf4j.Logger.ROOT_LOGGER_NAME);
        rootLogger.addAppender(this);
    }

    @Override
    protected void append(ILoggingEvent event) {
        // 排除請求日誌過濾器自身的日誌（避免循環）
        String loggerName = event.getLoggerName();
        if (loggerName != null && loggerName.startsWith("com.quantization.module.log")) {
            return;
        }

        // 排除第三方庫噪聲
        if (loggerName != null && (loggerName.startsWith("org.springframework.security")
                || loggerName.startsWith("org.hibernate")
                || loggerName.startsWith("com.zaxxer.hikari"))) {
            return;
        }

        String level = event.getLevel().levelStr;
        String message = event.getFormattedMessage();

        // 構建詳情
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("logger", loggerName);
        details.put("thread", event.getThreadName());
        if (event.getMarker() != null) {
            details.put("marker", event.getMarker().toString());
        }
        // 堆棧跟蹤
        if (event.getThrowableProxy() != null) {
            StringBuilder sb = new StringBuilder();
            sb.append(event.getThrowableProxy().getClassName());
            sb.append(": ").append(event.getThrowableProxy().getMessage());
            for (var frame : event.getThrowableProxy().getStackTraceElementProxyArray()) {
                sb.append("\n    at ").append(frame.getSTEAsString());
                if (sb.length() > 4000) {
                    sb.append("\n    ... (truncated)");
                    break;
                }
            }
            details.put("stackTrace", sb.toString());
        }

        LogEntry entry = new LogEntry(
                logMemoryStore.nextId("java"),
                "java",
                level,
                message,
                LocalDateTime.ofInstant(
                        java.time.Instant.ofEpochMilli(event.getTimeStamp()),
                        ZoneId.systemDefault()),
                details
        );
        logMemoryStore.add(entry);
    }
}
