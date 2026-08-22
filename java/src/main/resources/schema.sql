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
