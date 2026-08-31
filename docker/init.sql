-- ============================================================================
-- Trading Workstation — MySQL 容器初始化脚本
-- 由 docker-entrypoint-initdb.d 自动执行（仅首次创建数据卷时运行一次）
-- 包含：行情类 5 表 + ai_call_log + market_analysis_snapshot
-- schema.sql 中的表（user_preference / financial_news / chat_* 等）由 Java
-- 启动时幂等执行，此处不重复，避免 init.sql 与 schema.sql 维护两份。
-- ============================================================================

-- ===== 行情类 5 表（ingestion 写入）=====

CREATE TABLE IF NOT EXISTS stock_daily (
    id          BIGINT        NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)   NOT NULL,
    date        DATE          NOT NULL,
    open        DECIMAL(20,4),
    high        DECIMAL(20,4),
    low         DECIMAL(20,4),
    close       DECIMAL(20,4),
    preclose    DECIMAL(20,4),
    volume      BIGINT,
    amount      DECIMAL(30,2),
    adjustflag  INT           NOT NULL COMMENT '1=後復權/2=前復權/3=不復權',
    turn        DECIMAL(10,4),
    tradestatus INT,
    pctChg      DECIMAL(10,4),
    isST        INT,
    PRIMARY KEY (id),
    UNIQUE KEY uk_stock_daily (code, date, adjustflag),
    INDEX idx_adjustflag (adjustflag),
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS index_daily (
    id          BIGINT        NOT NULL AUTO_INCREMENT,
    code        VARCHAR(16)   NOT NULL,
    date        DATE          NOT NULL,
    open        DECIMAL(20,4),
    high        DECIMAL(20,4),
    low         DECIMAL(20,4),
    close       DECIMAL(20,4),
    preclose    DECIMAL(20,4),
    volume      BIGINT,
    amount      DECIMAL(30,2),
    pctChg      DECIMAL(12,6),
    frequency   VARCHAR(4)    NOT NULL DEFAULT 'd',
    source      VARCHAR(20)   DEFAULT 'baostock',
    PRIMARY KEY (id),
    UNIQUE KEY uk_index_daily (code, date, frequency),
    INDEX idx_index_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS index_metadata (
    id            BIGINT      NOT NULL AUTO_INCREMENT,
    code          VARCHAR(16) NOT NULL,
    name          VARCHAR(64),
    category      VARCHAR(32),
    category_code VARCHAR(32),
    source        VARCHAR(32),
    PRIMARY KEY (id),
    UNIQUE KEY uk_index_metadata_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stock_industry (
    id                       BIGINT      NOT NULL AUTO_INCREMENT,
    code                     VARCHAR(20) NOT NULL,
    update_date              DATE,
    code_name                VARCHAR(50),
    industry                 VARCHAR(100),
    industry_classification  VARCHAR(50),
    updated_at               TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_stock_industry_code (code),
    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS industry_daily (
    id            BIGINT        NOT NULL AUTO_INCREMENT,
    date          DATE          NOT NULL,
    industry      VARCHAR(100)  NOT NULL,
    stock_count   INT           NOT NULL DEFAULT 0,
    avg_pct_chg   DECIMAL(20,6),
    total_amount  DECIMAL(30,2),
    total_volume  BIGINT,
    avg_turn      DECIMAL(20,6),
    rising_count  INT           DEFAULT 0,
    falling_count INT           DEFAULT 0,
    avg_close     DECIMAL(20,4),
    max_close     DECIMAL(20,4),
    min_close     DECIMAL(20,4),
    created_at    TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_date_industry (date, industry),
    INDEX idx_date (date),
    INDEX idx_industry (industry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='行業日度聚合數據';

-- ===== ai_call_log（Agent LLM 调用日志）=====

CREATE TABLE IF NOT EXISTS ai_call_log (
    id                  BIGINT       NOT NULL AUTO_INCREMENT,
    iteration           INT          NOT NULL DEFAULT 0,
    stage_name          VARCHAR(64)  NOT NULL,
    stage_display_name  VARCHAR(128) NULL,
    provider            VARCHAR(32)  NULL,
    model_name          VARCHAR(64)  NULL,
    input_json          LONGTEXT     NULL,
    output_text         LONGTEXT     NULL,
    output_json         LONGTEXT     NULL,
    judge_score         DOUBLE       NULL,
    judge_passed        TINYINT(1)   NULL,
    judge_feedback      TEXT         NULL,
    attempts            INT          NULL DEFAULT 1,
    duration_ms         INT          NULL DEFAULT 0,
    error               TEXT         NULL,
    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_iteration (iteration),
    INDEX idx_stage (stage_name),
    INDEX idx_created (created_at),
    INDEX idx_score (judge_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- backtest_strategy 补充 source / result_json 列（幂等）
CREATE TABLE IF NOT EXISTS backtest_strategy (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    criteria_json   TEXT         NOT NULL,
    config_json     TEXT         NOT NULL,
    stats_json      TEXT,
    source          VARCHAR(20)  NOT NULL DEFAULT 'auto',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_backtest_strategy_source (source),
    INDEX idx_backtest_strategy_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===== market_analysis_snapshot（行情预计算快照）=====

CREATE TABLE IF NOT EXISTS market_analysis_snapshot (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    trade_date    DATE         NOT NULL,
    snapshot_type VARCHAR(50)  NOT NULL,
    snapshot_data JSON         NOT NULL,
    computed_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_version  VARCHAR(20)  NOT NULL DEFAULT '1.0',
    PRIMARY KEY (id),
    UNIQUE KEY uk_date_type (trade_date, snapshot_type),
    INDEX idx_trade_date (trade_date),
    INDEX idx_computed_at (computed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===== market_premarket_stats（盤前預計算統計）=====

CREATE TABLE IF NOT EXISTS market_premarket_stats (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    trade_date      DATE         NOT NULL,
    stat_type       VARCHAR(32)  NOT NULL,
    stat_key        VARCHAR(64)  NOT NULL,
    stat_value      TEXT,
    `rank`          INT,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_date_type_key (trade_date, stat_type, stat_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===== request_log（HTTP 請求日誌）=====

CREATE TABLE IF NOT EXISTS request_log (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    method          VARCHAR(10)  NOT NULL,
    request_path    VARCHAR(500) NOT NULL,
    query_string    VARCHAR(1000),
    status_code     INT,
    client_ip       VARCHAR(64),
    duration_ms     INT,
    content_length  BIGINT,
    user_agent      VARCHAR(500),
    error           VARCHAR(1000),
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_request_log_created (created_at),
    INDEX idx_request_log_path (request_path),
    INDEX idx_request_log_ip (client_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
