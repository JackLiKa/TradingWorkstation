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
    /** 指數元數據緩存名 */
    public static final String INDEX_METADATA_CACHE = "indexMetadata";
    /** 市場廣度緩存名 */
    public static final String MARKET_BREADTH_CACHE = "marketBreadth";
    /** 輪動信號緩存名 */
    public static final String ROTATION_SIGNAL_CACHE = "rotationSignal";
    /** 多日板塊表現緩存名 */
    public static final String SECTOR_PERFORMANCE_CACHE = "sectorPerformance";

    /**
     * 创建 Caffeine 缓存管理器，注册仪表盘、指數分析和板塊表現緩存。
     *
     * @param properties 应用配置属性
     * @return 配置好的 CaffeineCacheManager
     */
    @Bean
    public CacheManager cacheManager(AppProperties properties) {
        CaffeineCacheManager manager = new CaffeineCacheManager(
                SUMMARY_CACHE,
                METRICS_CACHE,
                INDEX_METADATA_CACHE,
                MARKET_BREADTH_CACHE,
                ROTATION_SIGNAL_CACHE,
                SECTOR_PERFORMANCE_CACHE
        );
        manager.setCaffeine(Caffeine.newBuilder()
                .expireAfterWrite(properties.getCache().getMetricsTtlSeconds(), TimeUnit.SECONDS)
                .maximumSize(500));
        return manager;
    }
}
