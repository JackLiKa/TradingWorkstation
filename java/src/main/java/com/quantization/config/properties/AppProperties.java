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
    private Preference preference = new Preference();
    private Chart chart = new Chart();

    /** 查询默认值配置（复权方式、条数限制、回看天数） */
    @Getter
    @Setter
    public static class QueryDefaults {
        private int adjustflag = 3;
        private int limit = 200;
        private int lookbackDays = 180;
    }

    /** 缓存 TTL 配置（按域分組，單位：秒） */
    @Getter
    @Setter
    public static class Cache {
        private long summaryTtlSeconds = 60;
        private long metricsTtlSeconds = 30;
        /** stock 行情查詢緩存 TTL（秒） */
        private long stockTtlSeconds = 30;
        /** industry 行業聚合/景氣度緩存 TTL（秒） */
        private long industryTtlSeconds = 60;
        /** forecast 預測/Markov 緩存 TTL（秒） */
        private long forecastTtlSeconds = 120;
        /** rotation 輪動緩存 TTL（秒） */
        private long rotationTtlSeconds = 120;
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

    /** 用户偏好配置（JSON 文件路径，支持相对/绝对路径） */
    @Getter
    @Setter
    public static class Preference {
        private String path = "preference.json";
    }

    /** K線圖配置（批次大小等） */
    @Getter
    @Setter
    public static class Chart {
        /** K線初始/歷史批次大小（每次加載的 K 線根數） */
        private int batchSize = 500;
    }
}
