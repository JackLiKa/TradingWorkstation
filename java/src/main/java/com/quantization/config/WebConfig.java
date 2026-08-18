package com.quantization.config;

import com.quantization.config.properties.AppProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.lang.NonNull;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web MVC 配置，设置 CORS 跨域策略。
 * <p>
 * 允许的来源由 {@link AppProperties.Cors} 配置，默认为前端开发地址。
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
     *
     * @param registry CORS 注册器
     */
    @Override
    public void addCorsMappings(@NonNull CorsRegistry registry) {
        String[] origins = properties.getCors().getAllowedOrigins().split(",");
        registry.addMapping("/api/**")
                .allowedOrigins(origins)
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }
}
