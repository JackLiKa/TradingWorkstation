-- 迁移脚本：为 financial_news 表添加 title_summary_hash 列和唯一约束
-- 用途：实现标题+摘要双层去重（即使 URI 不同，标题和摘要都相同也视为重复）
--
-- 执行方式（PowerShell 不支持 < 重定向，需用 Get-Content 管道）：
--   Get-Content java/scripts/migrate_news_title_summary_hash.sql -Raw | mysql -u root -p<password> a_stock_baostock
--
-- 或在 MySQL 客户端中直接执行以下 SQL：

-- 1. 添加 title_summary_hash 列（先允许 NULL，方便回填现有数据）
ALTER TABLE financial_news
    ADD COLUMN title_summary_hash VARCHAR(64) NULL AFTER summary;

-- 2. 回填现有数据的哈希值（SHA-256 of trimmed(title) + "|" + trimmed(summary)）
--    MySQL 8.0+ 支持 SHA2() 函数
UPDATE financial_news
SET title_summary_hash = SHA2(CONCAT(TRIM(IFNULL(title, '')), '|', TRIM(IFNULL(summary, ''))), 256)
WHERE title_summary_hash IS NULL;

-- 3. 将列改为 NOT NULL
ALTER TABLE financial_news
    MODIFY COLUMN title_summary_hash VARCHAR(64) NOT NULL;

-- 4. 清理重复记录（保留 id 较小的，即先入库的那条）
--    跳过此步如果步骤 5 失败，先执行此步再重试步骤 5
DELETE n1 FROM financial_news n1
INNER JOIN financial_news n2
ON n1.title_summary_hash = n2.title_summary_hash AND n1.id > n2.id;

-- 5. 添加唯一约束
ALTER TABLE financial_news
    ADD UNIQUE KEY uk_financial_news_title_summary (title_summary_hash);

-- 验证：确认无重复
-- SELECT title_summary_hash, COUNT(*) as cnt
-- FROM financial_news
-- GROUP BY title_summary_hash
-- HAVING cnt > 1;
-- 期望：0 行
