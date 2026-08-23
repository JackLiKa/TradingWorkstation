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
