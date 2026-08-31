package com.quantization.module.log;

import com.quantization.module.log.dto.LogEntry;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * HTTP 請求日誌過濾器 — 捕獲每個 API 請求的方法/路徑/狀態碼/IP/耗時，
 * 寫入內存緩衝（即時 SSE 推送）和 MySQL（異步持久化）。
 *
 * 過濾規則：
 * - 排除 /actuator 健康檢查（高頻無價值）
 * - 排除 /logs 端點自身（避免日誌頁面查詢產生自引用噪聲）
 * - 排除 swagger/openapi 靜態資源
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
public class RequestLoggingFilter extends OncePerRequestFilter {

    private final LogMemoryStore logMemoryStore;
    private final RequestLogRepository requestLogRepository;

    public RequestLoggingFilter(LogMemoryStore logMemoryStore, RequestLogRepository requestLogRepository) {
        this.logMemoryStore = logMemoryStore;
        this.requestLogRepository = requestLogRepository;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String path = request.getRequestURI();
        // 移除 context-path 前綴
        String contextPath = request.getContextPath();
        if (contextPath != null && !contextPath.equals("/") && path.startsWith(contextPath)) {
            path = path.substring(contextPath.length());
        }

        // 過濾噪聲路徑
        if (shouldSkip(path)) {
            filterChain.doFilter(request, response);
            return;
        }

        long startTime = System.currentTimeMillis();
        try {
            filterChain.doFilter(request, response);
        } finally {
            long duration = System.currentTimeMillis() - startTime;
            recordRequest(request, response, path, duration);
        }
    }

    private boolean shouldSkip(String path) {
        return path.startsWith("/actuator")
            || path.startsWith("/api/logs")          // 排除日誌端點自身
            || path.startsWith("/swagger-ui")
            || path.startsWith("/v3/api-docs")
            || path.startsWith("/favicon")
            || path.equals("/");
    }

    private void recordRequest(HttpServletRequest request, HttpServletResponse response,
                               String path, long durationMs) {
        String clientIp = extractClientIp(request);
        String method = request.getMethod();
        int statusCode = response.getStatus();
        String queryString = request.getQueryString();
        String userAgent = request.getHeader("User-Agent");
        long contentLength = request.getContentLengthLong();

        // 截斷 User-Agent
        if (userAgent != null && userAgent.length() > 500) {
            userAgent = userAgent.substring(0, 500);
        }

        // 1. 寫入內存緩衝（即時 SSE 推送）
        String level = statusCode >= 500 ? "ERROR" : statusCode >= 400 ? "WARN" : "INFO";
        String message = String.format("%s %s → %d (%dms) IP:%s",
                method, path, statusCode, durationMs, clientIp);
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("method", method);
        details.put("path", path);
        details.put("queryString", queryString);
        details.put("statusCode", statusCode);
        details.put("clientIp", clientIp);
        details.put("durationMs", durationMs);
        details.put("contentLength", contentLength);
        details.put("userAgent", userAgent);

        LogEntry entry = new LogEntry(
                logMemoryStore.nextId("system"),
                "system",
                level,
                message,
                LocalDateTime.now(),
                details
        );
        logMemoryStore.add(entry);

        // 2. 異步寫入 MySQL（持久化）
        try {
            RequestLogEntity entity = new RequestLogEntity();
            entity.setMethod(method);
            entity.setRequestPath(path);
            entity.setQueryString(queryString);
            entity.setStatusCode(statusCode);
            entity.setClientIp(clientIp);
            entity.setDurationMs((int) durationMs);
            entity.setContentLength(contentLength >= 0 ? contentLength : null);
            entity.setUserAgent(userAgent);
            entity.setCreatedAt(LocalDateTime.now());
            requestLogRepository.save(entity);
        } catch (Exception e) {
            // DB 寫入失敗不影響請求，僅記錄
            // 避免日誌過濾器自身日誌導致循環
        }
    }

    /** 提取客戶端真實 IP（優先 X-Forwarded-For / X-Real-IP） */
    private String extractClientIp(HttpServletRequest request) {
        String xff = request.getHeader("X-Forwarded-For");
        if (xff != null && !xff.isEmpty()) {
            // X-Forwarded-For 可能包含多個 IP，取第一個（最原始的客戶端）
            return xff.split(",")[0].trim();
        }
        String xRealIp = request.getHeader("X-Real-IP");
        if (xRealIp != null && !xRealIp.isEmpty()) {
            return xRealIp.trim();
        }
        return request.getRemoteAddr();
    }
}
