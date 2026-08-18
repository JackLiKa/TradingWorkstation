package com.quantization.module.screener;

import com.quantization.module.indicator.IndicatorConfig;
import com.quantization.module.indicator.IndicatorEngine;
import com.quantization.module.indicator.IndicatorSnapshot;
import com.quantization.module.screener.dto.ScreenedStockDto;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import com.quantization.module.stock.StockDaily;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 选股核心逻辑（高内聚）：分组、候选构建、条件过滤、排序。
 * 供 ScreenerService 与 BacktestService 复用，避免逻辑重复。
 */
@Component
public class ScreenerCore {

    private final IndicatorEngine indicatorEngine;

    public ScreenerCore(IndicatorEngine indicatorEngine) {
        this.indicatorEngine = indicatorEngine;
    }

    public record Grouped(Map<String, List<StockDaily>> histories, Map<String, List<LocalDate>> dates) {}

    public Grouped groupHistories(List<StockDaily> records) {
        Map<String, List<StockDaily>> grouped = new HashMap<>();
        for (StockDaily r : records) {
            grouped.computeIfAbsent(r.code(), k -> new ArrayList<>()).add(r);
        }
        Map<String, List<LocalDate>> dates = new HashMap<>();
        for (var e : grouped.entrySet()) {
            e.getValue().sort(Comparator.comparing(StockDaily::tradeDate));
            List<LocalDate> d = new ArrayList<>();
            for (StockDaily r : e.getValue()) d.add(r.tradeDate());
            dates.put(e.getKey(), d);
        }
        return new Grouped(grouped, dates);
    }

    public List<ScreenedStockDto> screenAt(Grouped grouped, LocalDate tradeDate, ScreenerCriteriaDto criteria, int limit) {
        // 指標最多需要 120 天，只取最近 150 天數據計算即可，避免對全部歷史算指標
        final int LOOKBACK = 150;
        // 並行計算：用 parallelStream 利用多核 CPU 加速指標計算
        List<ScreenedStockDto> candidates = grouped.histories.entrySet().parallelStream()
                .map(entry -> {
                    List<StockDaily> history = entry.getValue();
                    List<LocalDate> dates = grouped.dates.get(entry.getKey());
                    int endIdx = upperBound(dates, tradeDate);
                    if (endIdx <= 1 || !dates.get(endIdx - 1).equals(tradeDate)) return null;
                    // 只取最近 LOOKBACK 天的子列表，減少指標計算量
                    int startIdx = Math.max(0, endIdx - LOOKBACK);
                    List<StockDaily> slice = history.subList(startIdx, endIdx);
                    IndicatorSnapshot snapshot = indicatorEngine.buildSnapshot(entry.getKey(),
                            slice, IndicatorConfig.screener());
                    if (snapshot != null && ScreenerFilters.matches(snapshot, criteria)) {
                        return ScreenedStockDto.from(snapshot);
                    }
                    return null;
                })
                .filter(java.util.Objects::nonNull)
                .collect(java.util.stream.Collectors.toList());
        candidates.sort(sortComparator(criteria.sortBy()));
        return candidates.size() > limit ? candidates.subList(0, limit) : candidates;
    }

    public List<String> availableCodesOnDate(Grouped grouped, LocalDate rebalanceDate, LocalDate exitDate, boolean excludeSt) {
        List<String> available = new ArrayList<>();
        for (var entry : grouped.histories.entrySet()) {
            List<LocalDate> dates = grouped.dates.get(entry.getKey());
            int entryIdx = upperBound(dates, rebalanceDate) - 1;
            int exitIdx = upperBound(dates, exitDate) - 1;
            if (entryIdx < 0 || exitIdx <= entryIdx || !dates.get(entryIdx).equals(rebalanceDate)) continue;
            if (excludeSt && grouped.histories.get(entry.getKey()).get(entryIdx).isStStock()) continue;
            available.add(entry.getKey());
        }
        return available;
    }

    static int upperBound(List<LocalDate> dates, LocalDate key) {
        int lo = 0, hi = dates.size();
        while (lo < hi) {
            int mid = (lo + hi) >>> 1;
            if (dates.get(mid).compareTo(key) <= 0) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    private Comparator<ScreenedStockDto> sortComparator(String sortBy) {
        return (a, b) -> Double.compare(sortValue(b, sortBy), sortValue(a, sortBy));
    }

    private Double sortValue(ScreenedStockDto s, String sortBy) {
        try {
            java.lang.reflect.Field f = ScreenedStockDto.class.getDeclaredField(sortBy);
            f.setAccessible(true);
            Object value = f.get(s);
            if (value instanceof Number n) return n.doubleValue();
        } catch (Exception ignored) {
        }
        return Double.NEGATIVE_INFINITY;
    }
}
