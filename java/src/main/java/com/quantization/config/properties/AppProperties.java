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
    private Forecast forecast = new Forecast();

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

    /**
     * 預測引擎配置（滾動窗口集成權重適應）。
     * <p>
     * Phase 4 後續：生產預測可選啟用「滾動窗口逆 MAE 動態權重」，避免 look-ahead bias。
     * 默認關閉（{@code adaptive-weights=false}）以保持與歷史行為完全一致。
     */
    @Getter
    @Setter
    public static class Forecast {
        /**
         * 是否啟用滾動窗口自適應集成權重。
         * <p>
         * {@code false}（默認）：使用固定權重 ARIMA 0.35 / HW 0.35 / LR 0.30，行為與 Phase 4 一致。
         * {@code true}：用過去 {@link #rollingWindowDays} 天的滾動窗口計算各模型 one-step-ahead MAE，
         * 以逆 MAE 歸一化得到動態權重。計算只用截至預測日的歷史數據，不接觸未來數據（無 look-ahead bias）。
         */
        private boolean adaptiveWeights = false;

        /**
         * 滾動窗口天數（僅 {@code adaptive-weights=true} 時生效）。
         * <p>
         * 在此窗口內對每個時間點做 one-step-ahead 預測並累計各模型 MAE。默認 60 天。
         * 過大會平滑掉近期模型表現變化，過小會對噪聲過敏感。
         */
        private int rollingWindowDays = 60;
    }
}
