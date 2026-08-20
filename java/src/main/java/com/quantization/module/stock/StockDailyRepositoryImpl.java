package com.quantization.module.stock;

import com.quantization.common.util.CodeUtils;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.Tuple;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * 股票日线自定义查询实现，使用 JPA Criteria API 和原生 SQL 构建查询。
 * <p>
 * 包含数据库连通性检查、汇总指标、表格搜索、K线加载、波动榜、区间查询和搜索建议等。
 * </p>
 */
public class StockDailyRepositoryImpl implements StockDailyRepositoryCustom {

    @PersistenceContext
    private EntityManager em;

    /**
     * 数据库连通性检查，执行 SELECT 1。
     *
     * @return true 表示连接正常
     */
    @Override
    public boolean ping() {
        try {
            em.createNativeQuery("SELECT 1").getSingleResult();
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * 汇总指标：近似总行数、去重股票数、最新交易日及当日平均涨跌幅与成交额。
     *
     * @return 汇总指标投影
     */
    @Override
    public StockSummaryProjection summaryMetrics() {
        // 1. 最早 + 最新交易日（快速，走 idx_date 索引）
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<Tuple> dateQuery = cb.createTupleQuery();
        Root<StockDailyEntity> dr = dateQuery.from(StockDailyEntity.class);
        dateQuery.multiselect(
                cb.function("min", LocalDate.class, dr.get("tradeDate")).alias("earliest"),
                cb.function("max", LocalDate.class, dr.get("tradeDate")).alias("latest")
        );
        Tuple dateTuple = em.createQuery(dateQuery).getSingleResult();
        LocalDate earliest = dateTuple.get("earliest", LocalDate.class);
        LocalDate latest = dateTuple.get("latest", LocalDate.class);

        // 2. 近似总行数（SHOW TABLE STATUS，瞬间返回，误差 <1%）
        long approxTotal = approxTableRowCount();

        // 3. 去重股票数（走 uk_code_date_adjust 索引前缀，快速）
        CriteriaQuery<Long> symbolQuery = cb.createQuery(Long.class);
        Root<StockDailyEntity> sr = symbolQuery.from(StockDailyEntity.class);
        symbolQuery.select(cb.countDistinct(sr.get("code")));
        long totalSymbols = em.createQuery(symbolQuery).getSingleResult();

        // 4. 最新交易日平均涨跌幅 + 成交额（走 idx_date 索引）
        Double avgPct = null;
        Double turnover = null;
        if (latest != null) {
            CriteriaQuery<Tuple> q2 = cb.createTupleQuery();
            Root<StockDailyEntity> r2 = q2.from(StockDailyEntity.class);
            q2.multiselect(
                    cb.avg(r2.get("pctChange")).alias("avgPct"),
                    cb.sum(r2.get("amount")).alias("turnover")
            );
            q2.where(
                    cb.equal(r2.get("tradeDate"), latest),
                    cb.equal(r2.get("adjustflag"), 3)
            );
            Tuple t2 = em.createQuery(q2).getSingleResult();
            avgPct = toDouble(t2.get("avgPct"));
            turnover = toDouble(t2.get("turnover"));
        }

        return new StockSummaryProjection(approxTotal, totalSymbols, earliest, latest, avgPct, turnover);
    }

    /** 使用 SHOW TABLE STATUS 获取近似行数（毫秒级，12.9M 行表无需全表扫描）。 */
    private long approxTableRowCount() {
        try {
            var result = em.createNativeQuery("SHOW TABLE STATUS LIKE 'stock_daily'").getSingleResult();
            Object[] row = (Object[]) result;
            // 第 4 列为 Rows（近似值，InnoDB 误差通常 <1%）
            if (row.length > 4 && row[4] instanceof Number n) return n.longValue();
        } catch (Exception ignored) {
        }
        // 降级：精确 COUNT（慢但准确）
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<Long> cq = cb.createQuery(Long.class);
        cq.select(cb.count(cq.from(StockDailyEntity.class)));
        return em.createQuery(cq).getSingleResult();
    }

    /**
     * 日线表格查询：按 trade_date desc, code 排序，支持分页。
     * 无精确 code 且无日期范围时自动限定最新交易日，避免全表扫描。
     *
     * @param query 查询参数
     * @return 日线实体列表
     */
    @Override
    public List<StockDailyEntity> searchDaily(StockDailyQuery query) {
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<StockDailyEntity> cq = cb.createQuery(StockDailyEntity.class);
        Root<StockDailyEntity> r = cq.from(StockDailyEntity.class);
        List<Predicate> preds = basePredicates(cb, r, query);

        // 判斷是否為精確 code 匹配（完整代碼或6位數字）
        String code = CodeUtils.normalize(query.code());
        boolean isExactCode = CodeUtils.isFullCode(code) || CodeUtils.isPureSixDigit(code);

        // 無 code 或前綴匹配時，默認只查最新交易日，避免全表掃描排序
        // 精確 code 匹配則查全部歷史數據（用戶意圖是看個股歷史）
        if (!isExactCode && query.startDate() == null && query.endDate() == null) {
            CriteriaQuery<LocalDate> dateQuery = cb.createQuery(LocalDate.class);
            Root<StockDailyEntity> dr = dateQuery.from(StockDailyEntity.class);
            dateQuery.select(cb.function("max", LocalDate.class, dr.get("tradeDate")));
            LocalDate latest = em.createQuery(dateQuery).getSingleResult();
            if (latest != null) {
                preds.add(cb.equal(r.get("tradeDate"), latest));
            }
        }

        cq.where(preds.toArray(new Predicate[0]));
        cq.orderBy(cb.desc(r.get("tradeDate")), cb.asc(r.get("code")));
        var queryObj = em.createQuery(cq)
                .setMaxResults(query.limit())
                .setFirstResult(query.offset());
        return queryObj.getResultList();
    }

    /**
     * K线初始批次：指定 code，按 date desc 取 batchSize 条后正序返回。
     *
     * @param query     查询参数
     * @param batchSize 批次大小
     * @return 日线实体列表（按日期升序）
     */
    @Override
    public List<StockDailyEntity> candlestick(StockDailyQuery query, int batchSize) {
        if (query.code() == null || query.code().isBlank()) return List.of();
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<StockDailyEntity> cq = cb.createQuery(StockDailyEntity.class);
        Root<StockDailyEntity> r = cq.from(StockDailyEntity.class);
        cq.where(exactSymbolPredicates(cb, r, query).toArray(new Predicate[0]));
        cq.orderBy(cb.desc(r.get("tradeDate")));
        List<StockDailyEntity> rows = em.createQuery(cq).setMaxResults(batchSize).getResultList();
        rows.sort(Comparator.comparing(StockDailyEntity::getTradeDate));
        return rows;
    }

    /**
     * 更早历史批次：date < beforeDate，按 date desc 取 batchSize 条后正序返回。
     *
     * @param query      查询参数
     * @param beforeDate 截止日期
     * @param batchSize  批次大小
     * @return 日线实体列表（按日期升序）
     */
    @Override
    public List<StockDailyEntity> olderCandlestick(StockDailyQuery query, LocalDate beforeDate, int batchSize) {
        if (query.code() == null || query.code().isBlank()) return List.of();
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<StockDailyEntity> cq = cb.createQuery(StockDailyEntity.class);
        Root<StockDailyEntity> r = cq.from(StockDailyEntity.class);
        List<Predicate> preds = exactSymbolPredicates(cb, r, query);
        preds.add(cb.lessThan(r.get("tradeDate"), beforeDate));
        cq.where(preds.toArray(new Predicate[0]));
        cq.orderBy(cb.desc(r.get("tradeDate")));
        List<StockDailyEntity> rows = em.createQuery(cq).setMaxResults(batchSize).getResultList();
        rows.sort(Comparator.comparing(StockDailyEntity::getTradeDate));
        return rows;
    }

    /**
     * 最新交易日 |pctChg| 最大的若干只股票（不复权口径）。
     *
     * @param limit 返回条数
     * @return 日线实体列表
     */
    @Override
    public List<StockDailyEntity> latestMovers(int limit) {
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<LocalDate> dateQuery = cb.createQuery(LocalDate.class);
        Root<StockDailyEntity> dr = dateQuery.from(StockDailyEntity.class);
        dateQuery.select(cb.function("max", LocalDate.class, dr.get("tradeDate")));
        LocalDate latest = em.createQuery(dateQuery).getSingleResult();
        if (latest == null) return List.of();

        CriteriaQuery<StockDailyEntity> cq = cb.createQuery(StockDailyEntity.class);
        Root<StockDailyEntity> r = cq.from(StockDailyEntity.class);
        cq.where(
                cb.equal(r.get("tradeDate"), latest),
                cb.equal(r.get("adjustflag"), 3)
        );
        cq.orderBy(cb.desc(cb.abs(r.get("pctChange"))));
        return em.createQuery(cq).setMaxResults(limit).getResultList();
    }

    /**
     * 区间内去重交易日（升序）。
     *
     * @param start      起始日期
     * @param end        结束日期
     * @param adjustflag 复权方式
     * @return 交易日列表（升序）
     */
    @Override
    public List<LocalDate> tradeDates(LocalDate start, LocalDate end, int adjustflag) {
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<LocalDate> cq = cb.createQuery(LocalDate.class);
        Root<StockDailyEntity> r = cq.from(StockDailyEntity.class);
        cq.select(r.get("tradeDate")).distinct(true);
        cq.where(
                cb.greaterThanOrEqualTo(r.get("tradeDate"), start),
                cb.lessThanOrEqualTo(r.get("tradeDate"), end),
                cb.equal(r.get("adjustflag"), adjustflag)
        );
        cq.orderBy(cb.asc(r.get("tradeDate")));
        return em.createQuery(cq).getResultList();
    }

    /**
     * 区间内全部行情（按 code, date 升序），可限定 codes 列表。
     *
     * @param start      起始日期
     * @param end        结束日期
     * @param adjustflag 复权方式
     * @param codes      限定代码列表（null = 全部，空列表 = 返回空）
     * @return 日线实体列表
     */
    @Override
    public List<StockDailyEntity> recordsInRange(LocalDate start, LocalDate end, int adjustflag, List<String> codes) {
        if (codes != null && codes.isEmpty()) return List.of();
        CriteriaBuilder cb = em.getCriteriaBuilder();
        CriteriaQuery<StockDailyEntity> cq = cb.createQuery(StockDailyEntity.class);
        Root<StockDailyEntity> r = cq.from(StockDailyEntity.class);
        List<Predicate> preds = new ArrayList<>();
        preds.add(cb.greaterThanOrEqualTo(r.get("tradeDate"), start));
        preds.add(cb.lessThanOrEqualTo(r.get("tradeDate"), end));
        preds.add(cb.equal(r.get("adjustflag"), adjustflag));
        if (codes != null && !codes.isEmpty()) {
            preds.add(r.get("code").in(codes));
        }
        cq.where(preds.toArray(new Predicate[0]));
        cq.orderBy(cb.asc(r.get("code")), cb.asc(r.get("tradeDate")));
        return em.createQuery(cq).getResultList();
    }

    private List<Predicate> basePredicates(CriteriaBuilder cb, Root<StockDailyEntity> r, StockDailyQuery query) {
        List<Predicate> preds = new ArrayList<>();
        String code = CodeUtils.normalize(query.code());
        if (!code.isEmpty()) {
            preds.add(buildCodeFilter(cb, r, code));
        }
        if (query.adjustflag() > 0) {
            preds.add(cb.equal(r.get("adjustflag"), query.adjustflag()));
        }
        if (query.startDate() != null) {
            preds.add(cb.greaterThanOrEqualTo(r.get("tradeDate"), query.startDate()));
        }
        if (query.endDate() != null) {
            preds.add(cb.lessThanOrEqualTo(r.get("tradeDate"), query.endDate()));
        }
        return preds;
    }

    private List<Predicate> exactSymbolPredicates(CriteriaBuilder cb, Root<StockDailyEntity> r, StockDailyQuery query) {
        List<Predicate> preds = new ArrayList<>();
        String code = CodeUtils.normalize(query.code());
        if (CodeUtils.isPureSixDigit(code)) {
            // 6 位數字 → 展開為 sh./sz./bj. 精確匹配
            preds.add(r.get("code").in("sh." + code, "sz." + code, "bj." + code));
        } else {
            preds.add(cb.equal(r.get("code"), code));
        }
        if (query.adjustflag() > 0) {
            preds.add(cb.equal(r.get("adjustflag"), query.adjustflag()));
        }
        if (query.startDate() != null) {
            preds.add(cb.greaterThanOrEqualTo(r.get("tradeDate"), query.startDate()));
        }
        if (query.endDate() != null) {
            preds.add(cb.lessThanOrEqualTo(r.get("tradeDate"), query.endDate()));
        }
        return preds;
    }

    /**
     * 与原 Python _build_code_filter 语义对齐：
     * - 完整代码(含点且>=9) → 精确
     * - 6 位数字 → %.NNNNNN 模糊
     * - sh/sz 开头 → 前缀模糊
     * - 其它 → 双向模糊
     */
    private static Double toDouble(Object value) {
        if (value == null) return null;
        if (value instanceof Number n) return n.doubleValue();
        if (value instanceof BigDecimal bd) return bd.doubleValue();
        return null;
    }

    @SuppressWarnings("unchecked")
    private Predicate buildCodeFilter(CriteriaBuilder cb, Root<StockDailyEntity> r, String code) {
        if (CodeUtils.isFullCode(code)) {
            return cb.equal(r.get("code"), code);
        }
        if (CodeUtils.isPureSixDigit(code)) {
            // 6 位數字代碼 → 展開為 sh./sz. 精確匹配，走 idx_code 索引
            return r.get("code").in("sh." + code, "sz." + code, "bj." + code);
        }
        if (CodeUtils.startsWithMarket(code)) {
            // sh.600 / sz.000 等前綴 → LIKE 'sh.600%' 可走索引
            return cb.like(r.get("code"), code + "%");
        }
        // 部分數字代碼（如 600、0001）→ 展開為各市場前綴匹配，避免 '%.xxx%' 全表掃描
        String normalized = CodeUtils.normalize(code);
        if (normalized.chars().allMatch(Character::isDigit) && normalized.length() < 6) {
            return cb.or(
                    cb.like(r.get("code"), "sh." + normalized + "%"),
                    cb.like(r.get("code"), "sz." + normalized + "%"),
                    cb.like(r.get("code"), "bj." + normalized + "%")
            );
        }
        // 其他情況：前綴匹配（可走索引）
        return cb.like(r.get("code"), normalized + "%");
    }

    /**
     * 搜索建議：根據用戶輸入的部分代碼，返回最新交易日匹配的股票列表（含收盤價、漲跌幅）。
     *
     * @param query 搜索关键词
     * @param limit 返回条数
     * @return 日线实体列表
     */
    @Override
    @SuppressWarnings("unchecked")
    public List<StockDailyEntity> suggest(String query, int limit) {
        String q = CodeUtils.normalize(query);
        if (q.isEmpty()) return List.of();

        // 構建 code 匹配條件（與 buildCodeFilter 邏輯一致，但用於最新交易日）
        StringBuilder codeCondition = new StringBuilder();
        if (CodeUtils.isFullCode(q)) {
            codeCondition.append("code = '").append(q).append("'");
        } else if (CodeUtils.isPureSixDigit(q)) {
            codeCondition.append("code IN ('sh.").append(q).append("','sz.").append(q).append("','bj.").append(q).append("')");
        } else if (CodeUtils.startsWithMarket(q)) {
            codeCondition.append("code LIKE '").append(q).append("%'");
        } else if (q.chars().allMatch(Character::isDigit) && q.length() < 6) {
            codeCondition.append("(code LIKE 'sh.").append(q).append("%' OR code LIKE 'sz.").append(q).append("%' OR code LIKE 'bj.").append(q).append("%')");
        } else {
            codeCondition.append("code LIKE '").append(q).append("%'");
        }

        // 子查詢取最新交易日，主查詢在最新交易日內按 code 匹配 + 漲跌幅絕對值排序
        String sql = "SELECT * FROM stock_daily WHERE date = (SELECT MAX(date) FROM stock_daily) AND adjustflag = 3 AND " + codeCondition + " ORDER BY ABS(pctChg) DESC LIMIT " + limit;

        var nativeQuery = em.createNativeQuery(sql, StockDailyEntity.class);
        return nativeQuery.getResultList();
    }
}
