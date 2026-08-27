package com.quantization.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.lang.NonNull;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 安全響應頭攔截器 — 為所有 HTTP 響應添加安全頭。
 * <p>
 * 參考 jnuxky.xyz 安全兜底機制，防範 XSS / 點擊劫持 / MIME 嗅探：
 * <ul>
 *   <li>X-Frame-Options: DENY — 防止頁面被 iframe 嵌入（點擊劫持）</li>
 *   <li>X-Content-Type-Options: nosniff — 防止瀏覽器 MIME 嗅探</li>
 *   <li>X-XSS-Protection: 1; mode=block — 舊版瀏覽器 XSS 過濾</li>
 *   <li>Referrer-Policy: strict-origin-when-cross-origin — 限制 Referer 洩露</li>
 * </ul>
 * </p>
 */
public class SecurityHeadersInterceptor implements HandlerInterceptor {

    @Override
    public boolean preHandle(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull Object handler
    ) {
        response.setHeader("X-Frame-Options", "DENY");
        response.setHeader("X-Content-Type-Options", "nosniff");
        response.setHeader("X-XSS-Protection", "1; mode=block");
        response.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
        return true;
    }
}
