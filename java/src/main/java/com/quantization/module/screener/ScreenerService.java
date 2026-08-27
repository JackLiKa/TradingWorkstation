package com.quantization.module.screener;

import com.quantization.module.screener.dto.ScreenedStockDto;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import com.quantization.module.screener.dto.ScreenerResultDto;
import com.quantization.module.stock.StockDaily;
import com.quantization.module.stock.StockService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 选股服务，拉取区间行情数据，按条件筛选并排序，生成选股结果和摘要日志。
 */
@Service
@Transactional(readOnly = true)
public class ScreenerService {

    public static final int SCREENING_LOOKBACK_DAYS = 320;

    private final StockService stockService;
    private final ScreenerCore screenerCore;

    public ScreenerService(StockService stockService, ScreenerCore screenerCore) {
        this.stockService = stockService;
        this.screenerCore = screenerCore;
    }

    /**
     * 运行选股：拉取行情数据、归一化条件、筛选候选股票并生成摘要。
     *
     * @param raw 原始选股条件（字段可为 null，将自动填充默认值）
     * @return 选股结果 DTO
     */
    public ScreenerResultDto runScreener(ScreenerCriteriaDto raw) {
        ScreenerCriteriaDto criteria = normalize(raw);
        LocalDate start = criteria.asOfDate().minusDays(SCREENING_LOOKBACK_DAYS);
        List<StockDaily> records = stockService.domainRecordsInRange(start, criteria.asOfDate(), criteria.adjustflag(), null);
        if (records.isEmpty()) {
            return new ScreenerResultDto(criteria, null, 0, 0, List.of(), List.of(
                    "未读取到任何行情数据。",
                    "请检查日期范围、复权方式和数据库 stock_daily 表内容。"));
        }

        LocalDate screenDate = records.stream().map(StockDaily::tradeDate)
                .max(java.util.Comparator.naturalOrder()).orElse(null);
        ScreenerCore.Grouped grouped = screenerCore.groupHistories(records);

        // 统计扫描数（在 screenDate 当日有行情的股票数）
        int scanned = 0;
        for (var entry : grouped.histories().entrySet()) {
            List<LocalDate> dates = grouped.dates().get(entry.getKey());
            int endIdx = ScreenerCore.upperBound(dates, screenDate);
            if (endIdx > 1 && dates.get(endIdx - 1).equals(screenDate)) scanned++;
        }

        // 若指定了行業篩選，批量查詢最新行業分類
        Map<String, String> industryMap = buildIndustryMap(criteria.industries(), grouped.histories().keySet());

        List<ScreenedStockDto> candidates = screenerCore.screenAt(grouped, screenDate, criteria, criteria.maxResults(), industryMap);
        List<String> summary = buildSummary(criteria, screenDate, scanned, candidates);
        return new ScreenerResultDto(criteria, screenDate, scanned, candidates.size(), candidates, summary);
    }

    private List<String> buildSummary(ScreenerCriteriaDto criteria, LocalDate screenDate, int scanned, List<ScreenedStockDto> top) {
        List<String> lines = new ArrayList<>();
        lines.add("筛选基准日：" + screenDate);
        lines.add("扫描股票数：" + scanned + "，命中股票数：" + top.size());
        lines.add("排序字段：" + describeSortField(criteria.sortBy()) + "，最多展示 " + criteria.maxResults() + " 条");
        lines.add("当前条件：" + String.join("；", describeActiveConditions(criteria)));
        if (!screenDate.equals(criteria.asOfDate())) {
            lines.add("所选日期 " + criteria.asOfDate() + " 非交易日，已自动回退到最近交易日。");
        }
        if (!top.isEmpty()) {
            ScreenedStockDto first = top.get(0);
            lines.add("第一名：" + first.code() + "，评分 " + String.format("%.2f", first.score())
                    + "，MACD=" + describeCross(first.macdCrossSignal())
                    + "，KDJ=" + describeCross(first.kdjCrossSignal())
                    + "，BOLL=" + describeBoll(first.bollPosition()));
        } else {
            lines.add("当前条件过严，没有命中股票。建议放宽区间或信号限制。");
        }
        return lines;
    }

    private Map<String, String> buildIndustryMap(List<String> requested, Set<String> codes) {
        if (requested == null || requested.isEmpty() || codes == null || codes.isEmpty()) {
            return Map.of();
        }
        Map<String, String> map = new HashMap<>();
        for (Object[] row : stockService.findLatestIndustriesByCode(new ArrayList<>(codes))) {
            if (row[0] != null && row[1] != null) {
                map.put(row[0].toString(), row[1].toString());
            }
        }
        return map;
    }

    private String describeSortField(String sortBy) {
        return switch (sortBy) {
            case "score" -> "综合评分";
            case "pct_change" -> "当日涨跌幅";
            case "turn" -> "换手率";
            case "amplitude" -> "振幅";
            case "volume_ratio" -> "量比";
            case "return_20" -> "20日涨幅";
            case "return_60" -> "60日涨幅";
            case "return_120" -> "120日涨幅";
            case "rsi14" -> "RSI14";
            case "k_value" -> "K值";
            case "d_value" -> "D值";
            case "j_value" -> "J值";
            case "macd_hist" -> "MACD柱";
            case "boll_width" -> "BOLL带宽";
            case "boll_percent_b" -> "BOLL%B";
            default -> sortBy;
        };
    }

    private String describeCross(String value) {
        return switch (value) {
            case "golden_cross" -> "金叉";
            case "death_cross" -> "死叉";
            case "none" -> "无交叉";
            default -> "不限";
        };
    }

    private String describeBoll(String value) {
        return switch (value) {
            case "above_upper" -> "上轨外";
            case "upper_zone" -> "上轨区域";
            case "middle_upper" -> "中轨上方";
            case "middle_lower" -> "中轨下方";
            case "lower_zone" -> "下轨区域";
            case "below_lower" -> "下轨外";
            default -> "不限";
        };
    }

    private List<String> describeActiveConditions(ScreenerCriteriaDto c) {
        List<String> labels = new ArrayList<>();
        if (c.excludeSt() != null && c.excludeSt()) labels.add("排除ST");
        if (c.macdCrossSignal() != null && !"any".equals(c.macdCrossSignal())) {
            String label = "MACD信号=" + describeCross(c.macdCrossSignal());
            if (("golden_cross".equals(c.macdCrossSignal()) || "death_cross".equals(c.macdCrossSignal()))
                    && c.macdCrossWithinDays() != null && c.macdCrossWithinDays() > 0) {
                label += "(最近" + c.macdCrossWithinDays() + "日内)";
            }
            labels.add(label);
        }
        if (c.kdjCrossSignal() != null && !"any".equals(c.kdjCrossSignal())) {
            String label = "KDJ信号=" + describeCross(c.kdjCrossSignal());
            if (("golden_cross".equals(c.kdjCrossSignal()) || "death_cross".equals(c.kdjCrossSignal()))
                    && c.kdjCrossWithinDays() != null && c.kdjCrossWithinDays() > 0) {
                label += "(最近" + c.kdjCrossWithinDays() + "日内)";
            }
            labels.add(label);
        }
        if (c.bollPosition() != null && !"any".equals(c.bollPosition())) {
            labels.add("BOLL位置=" + describeBoll(c.bollPosition()));
        }
        if (Boolean.TRUE.equals(c.priceAboveMa5())) labels.add("收盘价站上MA5");
        if (Boolean.TRUE.equals(c.priceAboveMa20())) labels.add("收盘价站上MA20");
        if (Boolean.TRUE.equals(c.priceAboveMa60())) labels.add("收盘价站上MA60");
        if (Boolean.TRUE.equals(c.ma5AboveMa20())) labels.add("MA5高于MA20");
        if (Boolean.TRUE.equals(c.ma20AboveMa60())) labels.add("MA20高于MA60");
        if (c.industries() != null && !c.industries().isEmpty()) {
            labels.add("行業=" + String.join(",", c.industries()));
        }
        return labels.isEmpty() ? List.of("默认全市场筛选") : labels;
    }

    private ScreenerCriteriaDto normalize(ScreenerCriteriaDto r) {
        return new ScreenerCriteriaDto(
                r.asOfDate() == null ? LocalDate.now() : r.asOfDate(),
                r.adjustflag() == null ? 3 : r.adjustflag(),
                r.minClose() == null ? 0.0 : r.minClose(),
                r.maxClose() == null ? 100_000.0 : r.maxClose(),
                r.minPctChange() == null ? -100.0 : r.minPctChange(),
                r.maxPctChange() == null ? 100.0 : r.maxPctChange(),
                r.minTurn() == null ? 0.0 : r.minTurn(),
                r.maxTurn() == null ? 100.0 : r.maxTurn(),
                r.minAmplitude() == null ? 0.0 : r.minAmplitude(),
                r.maxAmplitude() == null ? 100.0 : r.maxAmplitude(),
                r.minVolume() == null ? 0L : r.minVolume(),
                r.minAmount() == null ? 0.0 : r.minAmount(),
                r.minVolumeRatio() == null ? 0.0 : r.minVolumeRatio(),
                r.maxVolumeRatio() == null ? 50.0 : r.maxVolumeRatio(),
                r.minReturn20() == null ? -100.0 : r.minReturn20(),
                r.maxReturn20() == null ? 500.0 : r.maxReturn20(),
                r.minReturn60() == null ? -100.0 : r.minReturn60(),
                r.maxReturn60() == null ? 1_000.0 : r.maxReturn60(),
                r.minReturn120() == null ? -100.0 : r.minReturn120(),
                r.maxReturn120() == null ? 2_000.0 : r.maxReturn120(),
                r.minRsi14() == null ? 0.0 : r.minRsi14(),
                r.maxRsi14() == null ? 100.0 : r.maxRsi14(),
                r.minKValue() == null ? 0.0 : r.minKValue(),
                r.maxKValue() == null ? 100.0 : r.maxKValue(),
                r.minDValue() == null ? 0.0 : r.minDValue(),
                r.maxDValue() == null ? 100.0 : r.maxDValue(),
                r.minJValue() == null ? -100.0 : r.minJValue(),
                r.maxJValue() == null ? 200.0 : r.maxJValue(),
                r.minMacdHist() == null ? -100.0 : r.minMacdHist(),
                r.maxMacdHist() == null ? 100.0 : r.maxMacdHist(),
                r.minBollWidth() == null ? 0.0 : r.minBollWidth(),
                r.maxBollWidth() == null ? 100.0 : r.maxBollWidth(),
                r.minBollPercentB() == null ? 0.0 : r.minBollPercentB(),
                r.maxBollPercentB() == null ? 100.0 : r.maxBollPercentB(),
                Boolean.TRUE.equals(r.priceAboveMa5()),
                Boolean.TRUE.equals(r.priceAboveMa20()),
                Boolean.TRUE.equals(r.priceAboveMa60()),
                Boolean.TRUE.equals(r.ma5AboveMa20()),
                Boolean.TRUE.equals(r.ma20AboveMa60()),
                r.macdCrossSignal() == null ? "any" : r.macdCrossSignal(),
                r.macdCrossWithinDays() == null ? 0 : r.macdCrossWithinDays(),
                r.kdjCrossSignal() == null ? "any" : r.kdjCrossSignal(),
                r.kdjCrossWithinDays() == null ? 0 : r.kdjCrossWithinDays(),
                r.bollPosition() == null ? "any" : r.bollPosition(),
                r.excludeSt() == null ? true : r.excludeSt(),
                r.maxResults() == null ? 100 : r.maxResults(),
                r.sortBy() == null ? "score" : r.sortBy(),
                r.industries() == null ? List.of() : r.industries()
        );
    }
}
