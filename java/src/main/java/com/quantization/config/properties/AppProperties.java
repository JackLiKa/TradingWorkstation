package com.quantization.config.properties;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 应用配置属性，绑定 {@code app.*} 前缀的配置项。
 * <p>
 * 包含查询默认值、缓存 TTL、CORS 允许来源和数据同步等子配置。
 * </p>
 */
@Getter
@Setter
@Component
@ConfigurationProperties(prefix = "app")
public class AppProperties {
    private String title;
    private QueryDefaults queryDefaults = new QueryDefaults();
    private Cache cache = new Cache();
    private Cors cors = new Cors();
    private Sync sync = new Sync();

    /** 查询默认值配置（复权方式、条数限制、回看天数） */
    @Getter
    @Setter
    public static class QueryDefaults {
        private int adjustflag = 3;
        private int limit = 200;
        private int lookbackDays = 180;
    }

    /** 缓存 TTL 配置（汇总缓存和指标缓存，单位：秒） */
    @Getter
    @Setter
    public static class Cache {
        private long summaryTtlSeconds = 60;
        private long metricsTtlSeconds = 30;
    }

    /** CORS 跨域配置（允许的来源列表，逗号分隔） */
    @Getter
    @Setter
    public static class Cors {
        private String allowedOrigins = "http://localhost:3010";
    }

    /** 数据同步配置（Python 路径、脚本路径、批次大小、默认起始日期） */
    @Getter
    @Setter
    public static class Sync {
        private String pythonExecutable = "python";
        private String ingestionScript = "ingestion/baostock_ingest.py";
        private int batchSize = 1000;
        private String defaultStartDate = "2021-01-01";
    }
}
