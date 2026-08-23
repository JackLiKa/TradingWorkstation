-- 用户偏好表：替代 preference.json 文件存储，支持多实例部署。
-- 幂等建表，每次启动安全执行。
CREATE TABLE IF NOT EXISTS user_preference (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    user_id         VARCHAR(64)  NOT NULL,
    preference_json TEXT,
    created_at      DATETIME     NOT NULL,
    updated_at      DATETIME     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_preference_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 财经新闻表：存储华尔街见闻等来源的财经新闻。
-- URI 去重：同一文章不会重复入库。
CREATE TABLE IF NOT EXISTS financial_news (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    uri           VARCHAR(200) NOT NULL,
    title         VARCHAR(500) NOT NULL,
    summary       VARCHAR(2000),
    content       TEXT,
    source        VARCHAR(50)  NOT NULL,
    author        VARCHAR(100),
    channel       VARCHAR(50),
    published_at  DATETIME,
    url           VARCHAR(500),
    image_url     VARCHAR(500),
    created_at    DATETIME     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_financial_news_uri (uri),
    INDEX idx_financial_news_channel (channel),
    INDEX idx_financial_news_published (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 财经新闻情感评分表：存储 LLM reranker 的双维度评分结果。
-- 用于建立「利好池」「利空池」，策略生成时只从利好池选股。
-- 自我成长机制：每次 reranker 评分都持久化，历史评分可复用。
CREATE TABLE IF NOT EXISTS news_sentiment_score (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    uri             VARCHAR(200) NOT NULL,
    title           VARCHAR(500) NOT NULL,
    direction       INT          NOT NULL,          -- -10 到 +10（利好/利空方向）
    sustainability  INT          NOT NULL,          -- 0 到 10（持续性评分）
    composite_score DECIMAL(5,2) NOT NULL,          -- direction * sustainability / 10
    news_label      VARCHAR(20)  NOT NULL,          -- 持续性利好/一日遊利好/弱利好/中性/弱利空/持续性利空/一日遊利空
    query_context   VARCHAR(500),                   -- 评分时的查询上下文
    scored_at       DATETIME     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_news_sentiment_uri_query (uri, query_context(100)),
    INDEX idx_news_sentiment_label (news_label),
    INDEX idx_news_sentiment_direction (direction),
    INDEX idx_news_sentiment_scored (scored_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 股票上市状态表：用于消除倖存者偏差（回测时按日期过滤在市股票）。
-- 记录每只股票的上市日期、退市日期和板块信息。
CREATE TABLE IF NOT EXISTS stock_listing (
    code            VARCHAR(20)  NOT NULL,
    code_name       VARCHAR(50),
    board           VARCHAR(10)  NOT NULL COMMENT 'main/star/chinext/st',
    listing_date    DATE,
    delisting_date  DATE,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (code),
    INDEX idx_stock_listing_board (board),
    INDEX idx_stock_listing_dates (listing_date, delisting_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 回测策略存储表：记录优化器生成的策略及其回测结果。
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
