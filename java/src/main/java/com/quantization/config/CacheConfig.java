package com.quantization.config;

import com.quantization.config.properties.AppProperties;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.cache.caffeine.CaffeineCache;
import org.springframework.cache.support.SimpleCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.TimeUnit;

/**
 * Caffeine 缓存配置，按域分組管理多個獨立 TTL 的緩存。
 * <p>
 * 緩存 TTL 由 {@link AppProperties.Cache} 控制，最大緩存條目 500。
 * 各緩存按業務域命名，避免跨域相互擠占。
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
    /** 輪動信號緩存名（stock 模塊的輪動信號查詢） */
    public static final String ROTATION_SIGNAL_CACHE = "rotationSignal";
    /** 多日板塊表現緩存名 */
    public static final String SECTOR_PERFORMANCE_CACHE = "sectorPerformance";
    /** stock 模塊行情查詢緩存名 */
    public static final String STOCK_DAILY_CACHE = "stockDaily";
    /** industry 模塊行業聚合/景氣度緩存名 */
    public static final String INDUSTRY_DAILY_CACHE = "industryDaily";
    /** forecast 模塊預測/Markov 緩存名 */
    public static final String FORECAST_CACHE = "forecast";
    /** forecast 模塊輪動預測緩存名 */
    public static final String ROTATION_CACHE = "rotation";

    /**
     * 创建 Caffeine 缓存管理器，为不同缓存配置独立 TTL：
     * <ul>
     *   <li>{@code dashboardSummary}：{@code summaryTtlSeconds}（默认 60s）</li>
     *   <li>{@code dashboardMetrics}、{@code indexMetadata}、{@code marketBreadth}、
     *       {@code rotationSignal}、{@code sectorPerformance}：{@code metricsTtlSeconds}（默认 30s）</li>
     *   <li>{@code stockDaily}：{@code stockTtlSeconds}（默认 30s）</li>
     *   <li>{@code industryDaily}：{@code industryTtlSeconds}（默认 60s）</li>
     *   <li>{@code forecast}：{@code forecastTtlSeconds}（默认 120s）</li>
     *   <li>{@code rotation}：{@code rotationTtlSeconds}（默认 120s）</li>
     * </ul>
     * 所有缓存 maximumSize=500。
     *
     * @param properties 应用配置属性
     * @return 配置好的 SimpleCacheManager（每个缓存独立 Caffeine spec）
     */
    @Bean
    public CacheManager cacheManager(AppProperties properties) {
        AppProperties.Cache c = properties.getCache();
        long summaryTtl = c.getSummaryTtlSeconds();
        long metricsTtl = c.getMetricsTtlSeconds();
        long stockTtl = c.getStockTtlSeconds();
        long industryTtl = c.getIndustryTtlSeconds();
        long forecastTtl = c.getForecastTtlSeconds();
        long rotationTtl = c.getRotationTtlSeconds();

        SimpleCacheManager manager = new SimpleCacheManager();
        manager.setCaches(java.util.List.of(
                buildCache(SUMMARY_CACHE, summaryTtl),
                buildCache(METRICS_CACHE, metricsTtl),
                buildCache(INDEX_METADATA_CACHE, metricsTtl),
                buildCache(MARKET_BREADTH_CACHE, metricsTtl),
                buildCache(ROTATION_SIGNAL_CACHE, metricsTtl),
                buildCache(SECTOR_PERFORMANCE_CACHE, metricsTtl),
                buildCache(STOCK_DAILY_CACHE, stockTtl),
                buildCache(INDUSTRY_DAILY_CACHE, industryTtl),
                buildCache(FORECAST_CACHE, forecastTtl),
                buildCache(ROTATION_CACHE, rotationTtl)
        ));
        return manager;
    }

    private static Cache buildCache(String name, long ttlSeconds) {
        return new CaffeineCache(name, Caffeine.newBuilder()
                .expireAfterWrite(ttlSeconds, TimeUnit.SECONDS)
                .maximumSize(500)
                .build());
    }
}
