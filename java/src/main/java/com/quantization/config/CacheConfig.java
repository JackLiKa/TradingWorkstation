package com.quantization.config;

import com.quantization.config.properties.AppProperties;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.cache.CacheManager;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.TimeUnit;

/**
 * Caffeine 缓存配置，管理仪表盘汇总数据和指标的两个缓存。
 * <p>
 * 缓存 TTL 由 {@link AppProperties.Cache} 控制，最大缓存条目 500。
 * </p>
 */
@Configuration
public class CacheConfig {

    /** 仪表盘汇总数据缓存名 */
    public static final String SUMMARY_CACHE = "dashboardSummary";
    /** 仪表盘指标缓存名 */
    public static final String METRICS_CACHE = "dashboardMetrics";

    /**
     * 创建 Caffeine 缓存管理器，注册汇总和指标两个缓存。
     *
     * @param properties 应用配置属性
     * @return 配置好的 CaffeineCacheManager
     */
    @Bean
    public CacheManager cacheManager(AppProperties properties) {
        CaffeineCacheManager manager = new CaffeineCacheManager(SUMMARY_CACHE, METRICS_CACHE);
        manager.setCaffeine(Caffeine.newBuilder()
                .expireAfterWrite(properties.getCache().getMetricsTtlSeconds(), TimeUnit.SECONDS)
                .maximumSize(500));
        return manager;
    }
}
