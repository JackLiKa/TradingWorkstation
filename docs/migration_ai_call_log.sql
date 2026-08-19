-- AI call log table + backtest_strategy extension
-- Run: mysql -u root -p a_stock_baostock < docs/migration_ai_call_log.sql

CREATE TABLE IF NOT EXISTS ai_call_log (
  id BIGINT NOT NULL AUTO_INCREMENT,
  iteration INT NOT NULL DEFAULT 0,
  stage_name VARCHAR(64) NOT NULL,
  stage_display_name VARCHAR(128) NULL,
  provider VARCHAR(32) NULL,
  model_name VARCHAR(64) NULL,
  input_json LONGTEXT NULL,
  output_text LONGTEXT NULL,
  output_json LONGTEXT NULL,
  judge_score DOUBLE NULL,
  judge_passed TINYINT(1) NULL,
  judge_feedback TEXT NULL,
  attempts INT NULL DEFAULT 1,
  duration_ms INT NULL DEFAULT 0,
  error TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_iteration (iteration),
  KEY idx_stage (stage_name),
  KEY idx_created (created_at),
  KEY idx_score (judge_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE backtest_strategy ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'manual' AFTER status;
ALTER TABLE backtest_strategy ADD COLUMN IF NOT EXISTS result_json LONGTEXT NULL AFTER config_json;
