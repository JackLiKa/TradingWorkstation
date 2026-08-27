package com.quantization.config;

import com.quantization.config.properties.AppProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.lang.NonNull;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web MVC 配置，设置 CORS 跨域策略和安全响应头。
 * <p>
 * 允许的来源由 {@link AppProperties.Cors} 配置，默认为前端开发地址。
 * 安全头參考 jnuxky.xyz 安全兜底機制：X-Frame-Options / X-Content-Type-Options / X-XSS-Protection / Referrer-Policy。
 * </p>
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final AppProperties properties;

    public WebConfig(AppProperties properties) {
        this.properties = properties;
    }

    /**
     * 配置 CORS 跨域映射，对 /api/** 路径开放指定来源的跨域访问。
     * 不使用通配符 "*"，明確列出允許的來源。
     *
     * @param registry CORS 注册器
     */
    @Override
    public void addCorsMappings(@NonNull CorsRegistry registry) {
        String[] origins = properties.getCors().getAllowedOrigins().split(",");
        registry.addMapping("/api/**")
                .allowedOrigins(origins)
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("Content-Type", "Authorization", "X-Requested-With", "X-Webhook-Signature")
                .allowCredentials(true)
                .maxAge(3600);
    }

    /**
     * 註冊安全頭攔截器 — 為所有響應添加安全頭。
     *
     * @param registry 攔截器註冊器
     */
    @Override
    public void addInterceptors(@NonNull InterceptorRegistry registry) {
        registry.addInterceptor(new SecurityHeadersInterceptor())
                .addPathPatterns("/**");
    }
}
