package com.quantization.module.industry;

import com.quantization.config.CacheConfig;
import com.quantization.module.stock.IndustryDailyEntity;
import com.quantization.module.stock.IndustryDailyRepository;
import com.quantization.module.stock.StockMathUtils;
import com.quantization.module.stock.dto.IndustryDailyDto;
import com.quantization.module.stock.dto.IndustryProsperityDto;
import com.quantization.module.stock.dto.ProsperityAlertDto;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 行業服務，封裝行業日聚合查詢、景氣度計算與異常預警等業務邏輯。
 */
@Service
@Transactional(readOnly = true)
public class IndustryService {

    private final IndustryDailyRepository industryDailyRepository;

    public IndustryService(IndustryDailyRepository industryDailyRepository) {
        this.industryDailyRepository = industryDailyRepository;
    }

    // ------------------------------------------------------------------------
    // 行業日聚合
    // ------------------------------------------------------------------------

    /**
     * 查詢指定日期的行業聚合數據，按平均漲跌幅倒序（走緩存）。
     *
     * @param tradeDate 交易日期，為空時取資料庫最新交易日
     * @return 行業聚合 DTO 列表
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "#p0 != null ? #p0.toString() : 'latest'")
    public List<IndustryDailyDto> industryDailyByDate(LocalDate tradeDate) {
        LocalDate target = tradeDate != null ? tradeDate : latestIndustryDailyDate();
        return industryDailyRepository.findByTradeDateOrderByAvgPctChgDesc(target).stream()
                .map(IndustryDailyDto::from)
                .toList();
    }

    private LocalDate latestIndustryDailyDate() {
        IndustryDailyEntity latest = industryDailyRepository.findFirstByOrderByTradeDateDesc();
        return latest != null ? latest.getTradeDate() : LocalDate.now();
    }

    /**
     * 查詢指定行業在日期區間內的聚合數據，按日期升序（走緩存）。
     *
     * @param industry 行業名稱
     * @param start    起始日期
     * @param end      結束日期
     * @return 行業聚合 DTO 列表
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "#p0 + '-' + #p1 + '-' + #p2")
    public List<IndustryDailyDto> industryDailyRange(String industry, LocalDate start, LocalDate end) {
        return industryDailyRepository.findByIndustryAndTradeDateBetweenOrderByTradeDateAsc(
                        industry, start, end).stream()
                .map(IndustryDailyDto::from)
                .toList();
    }

    /**
     * 查詢日期區間內全部行業的聚合數據（用於行業相關性矩陣計算）。
     *
     * @param start 起始日期
     * @param end   結束日期
     * @return 全部行業聚合 DTO 列表（按日期升序、行業升序）
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'all-' + #p0 + '-' + #p1")
    public List<IndustryDailyDto> allIndustryDailyRange(LocalDate start, LocalDate end) {
        return industryDailyRepository.findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(
                        start, end).stream()
                .map(IndustryDailyDto::from)
                .toList();
    }

    // ------------------------------------------------------------------------
    // 行業景氣度
    // ------------------------------------------------------------------------

    /**
     * 計算指定日期的行業景氣度指標（基於漲跌幅、成交額、換手率、漲跌家數綜合評分）。
     *
     * 評分維度（每維 0-100，加權綜合為 prosperityIndex）：
     * - momentumScore (權重 0.35): avgPctChg 標準化
     * - capitalScore (權重 0.25): totalAmount 標準化
     * - activityScore (權重 0.20): avgTurn 標準化
     * - breadthScore (權重 0.20): risingCount / (risingCount + fallingCount) 標準化
     *
     * @param tradeDate 交易日期，為空時取最新交易日
     * @return 行業景氣度 DTO 列表（按 prosperityIndex 倒序）
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'prosperity-' + (#p0 != null ? #p0.toString() : 'latest')")
    public List<IndustryProsperityDto> industryProsperity(LocalDate tradeDate) {
        LocalDate target = tradeDate != null ? tradeDate : latestIndustryDailyDate();
        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateOrderByAvgPctChgDesc(target);

        if (entities.isEmpty()) {
            return List.of();
        }

        // 提取各維度數據用於標準化
        double[] pctChgs = entities.stream()
                .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0)
                .toArray();
        double[] amounts = entities.stream()
                .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                .toArray();
        double[] turns = entities.stream()
                .mapToDouble(e -> e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0)
                .toArray();
        double[] breadths = entities.stream()
                .mapToDouble(e -> {
                    int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
                    int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
                    int total = rising + falling;
                    return total > 0 ? (double) rising / total * 100.0 : 50.0;
                })
                .toArray();

        // 計算各維度的 min/max 用於標準化
        double pctMin = StockMathUtils.min(pctChgs), pctMax = StockMathUtils.max(pctChgs);
        double amtMin = StockMathUtils.min(amounts), amtMax = StockMathUtils.max(amounts);
        double turnMin = StockMathUtils.min(turns), turnMax = StockMathUtils.max(turns);
        double breadthMin = StockMathUtils.min(breadths), breadthMax = StockMathUtils.max(breadths);

        return entities.stream().map(e -> {
            double pctChg = e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0;
            double amount = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
            double turn = e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0;
            int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
            int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
            int total = rising + falling;
            double breadth = total > 0 ? (double) rising / total * 100.0 : 50.0;

            // 標準化到 0-100
            double momentumScore = StockMathUtils.normalize(pctChg, pctMin, pctMax);
            double capitalScore = StockMathUtils.normalize(amount, amtMin, amtMax);
            double activityScore = StockMathUtils.normalize(turn, turnMin, turnMax);
            double breadthScore = StockMathUtils.normalize(breadth, breadthMin, breadthMax);

            // 加權綜合
            double prosperityIndex = momentumScore * 0.35
                    + capitalScore * 0.25
                    + activityScore * 0.20
                    + breadthScore * 0.20;

            String grade = StockMathUtils.prosperityGrade(prosperityIndex);

            return new IndustryProsperityDto(
                    e.getTradeDate(),
                    e.getIndustry(),
                    pctChg,
                    amount,
                    turn,
                    rising,
                    falling,
                    Math.round(momentumScore * 100.0) / 100.0,
                    Math.round(capitalScore * 100.0) / 100.0,
                    Math.round(activityScore * 100.0) / 100.0,
                    Math.round(breadthScore * 100.0) / 100.0,
                    Math.round(prosperityIndex * 100.0) / 100.0,
                    grade
            );
        }).sorted((a, b) -> Double.compare(b.prosperityIndex(), a.prosperityIndex())).toList();
    }

    /**
     * 計算日期區間內每個交易日的行業景氣度（用於歷史趨勢圖）。
     *
     * @param start 起始日期
     * @param end   結束日期
     * @param topN  每個日期返回的行業數（按景氣度倒序），默認 15
     * @return 行業景氣度 DTO 列表（按日期升序、景氣度倒序）
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'prosperity-range-' + #p0 + '-' + #p1 + '-' + #p2")
    public List<IndustryProsperityDto> industryProsperityRange(LocalDate start, LocalDate end, int topN) {
        List<IndustryDailyEntity> allEntities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (allEntities.isEmpty()) {
            return List.of();
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : allEntities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<IndustryProsperityDto> result = new ArrayList<>();
        for (Map.Entry<LocalDate, List<IndustryDailyEntity>> entry : byDate.entrySet()) {
            List<IndustryDailyEntity> entities = entry.getValue();

            // 提取各維度數據用於標準化
            double[] pctChgs = entities.stream()
                    .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0)
                    .toArray();
            double[] amounts = entities.stream()
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .toArray();
            double[] turns = entities.stream()
                    .mapToDouble(e -> e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0)
                    .toArray();
            double[] breadths = entities.stream()
                    .mapToDouble(e -> {
                        int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
                        int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
                        int total = rising + falling;
                        return total > 0 ? (double) rising / total * 100.0 : 50.0;
                    })
                    .toArray();

            double pctMin = StockMathUtils.min(pctChgs), pctMax = StockMathUtils.max(pctChgs);
            double amtMin = StockMathUtils.min(amounts), amtMax = StockMathUtils.max(amounts);
            double turnMin = StockMathUtils.min(turns), turnMax = StockMathUtils.max(turns);
            double breadthMin = StockMathUtils.min(breadths), breadthMax = StockMathUtils.max(breadths);

            List<IndustryProsperityDto> dayResults = entities.stream().map(e -> {
                double pctChg = e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0;
                double amount = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
                double turn = e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0;
                int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
                int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
                int total = rising + falling;
                double breadth = total > 0 ? (double) rising / total * 100.0 : 50.0;

                double momentumScore = StockMathUtils.normalize(pctChg, pctMin, pctMax);
                double capitalScore = StockMathUtils.normalize(amount, amtMin, amtMax);
                double activityScore = StockMathUtils.normalize(turn, turnMin, turnMax);
                double breadthScore = StockMathUtils.normalize(breadth, breadthMin, breadthMax);

                double prosperityIndex = momentumScore * 0.35
                        + capitalScore * 0.25
                        + activityScore * 0.20
                        + breadthScore * 0.20;

                String grade = StockMathUtils.prosperityGrade(prosperityIndex);

                return new IndustryProsperityDto(
                        e.getTradeDate(),
                        e.getIndustry(),
                        pctChg,
                        amount,
                        turn,
                        rising,
                        falling,
                        Math.round(momentumScore * 100.0) / 100.0,
                        Math.round(capitalScore * 100.0) / 100.0,
                        Math.round(activityScore * 100.0) / 100.0,
                        Math.round(breadthScore * 100.0) / 100.0,
                        Math.round(prosperityIndex * 100.0) / 100.0,
                        grade
                );
            }).sorted((a, b) -> Double.compare(b.prosperityIndex(), a.prosperityIndex()))
                    .limit(topN)
                    .toList();

            result.addAll(dayResults);
        }

        return result;
    }

    // ------------------------------------------------------------------------
    // 行業景氣度異常預警
    // ------------------------------------------------------------------------

    /**
     * 行業景氣度異常預警 — 檢測最新交易日 vs 前一交易日的景氣度突變與等級躍遷。
     *
     * 預警類型：
     * 1. surge（景氣度突升）：變化 ≥ threshold
     * 2. plunge（景氣度突降）：變化 ≤ -threshold
     * 3. grade_up（等級躍升）：等級從低到高
     * 4. grade_down（等級躍降）：等級從高到低
     *
     * @param threshold 突變閾值（默認 10.0）
     * @return 景氣度預警 DTO
     */
    @Cacheable(value = CacheConfig.INDUSTRY_DAILY_CACHE, key = "'prosperity-alert-' + #p0")
    public ProsperityAlertDto prosperityAlerts(double threshold) {
        LocalDate today = LocalDate.now();
        LocalDate start = today.minusDays(10);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, today);

        if (entities.isEmpty()) {
            return new ProsperityAlertDto(today.toString(), List.of(), "數據不足，無法檢測異常");
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < 2) {
            return new ProsperityAlertDto(today.toString(), List.of(), "交易日不足，無法對比");
        }

        LocalDate latestDate = sortedDates.get(sortedDates.size() - 1);
        LocalDate prevDate = sortedDates.get(sortedDates.size() - 2);

        List<IndustryDailyEntity> todayEntities = byDate.get(latestDate);
        List<IndustryDailyEntity> yesterdayEntities = byDate.get(prevDate);

        // 計算今日和昨日的景氣度
        Map<String, Double> todayProsperity = computeProsperityMap(todayEntities);
        Map<String, Double> yesterdayProsperity = computeProsperityMap(yesterdayEntities);

        List<ProsperityAlertDto.AlertEntry> alerts = new ArrayList<>();

        for (String industry : todayProsperity.keySet()) {
            Double todayVal = todayProsperity.get(industry);
            Double yesterdayVal = yesterdayProsperity.get(industry);
            if (todayVal == null || yesterdayVal == null) continue;

            double change = todayVal - yesterdayVal;
            String todayGrade = StockMathUtils.prosperityGrade(todayVal);
            String yesterdayGrade = StockMathUtils.prosperityGrade(yesterdayVal);

            String alertType = null;
            String alertTypeName = null;
            String severity = null;

            // 景氣度突升
            if (change >= threshold * 2) {
                alertType = "surge";
                alertTypeName = "景氣度突升";
                severity = "high";
            } else if (change >= threshold) {
                alertType = "surge";
                alertTypeName = "景氣度上升";
                severity = "medium";
            }

            // 景氣度突降
            if (change <= -threshold * 2) {
                alertType = "plunge";
                alertTypeName = "景氣度突降";
                severity = "high";
            } else if (change <= -threshold && alertType == null) {
                alertType = "plunge";
                alertTypeName = "景氣度下降";
                severity = "medium";
            }

            // 等級躍遷
            int todayGradeLevel = StockMathUtils.gradeLevel(todayGrade);
            int yesterdayGradeLevel = StockMathUtils.gradeLevel(yesterdayGrade);
            if (todayGradeLevel > yesterdayGradeLevel) {
                // 等級躍升（如 低迷 → 景氣）
                if (todayGradeLevel - yesterdayGradeLevel >= 2) {
                    alerts.add(new ProsperityAlertDto.AlertEntry(
                            industry, "grade_up", "等級躍升",
                            Math.round(yesterdayVal * 100.0) / 100.0,
                            Math.round(todayVal * 100.0) / 100.0,
                            Math.round(change * 100.0) / 100.0,
                            yesterdayGrade, todayGrade, "high",
                            String.format("%s 等級從「%s」躍升到「%s」（景氣度 %.1f → %.1f）",
                                    industry, yesterdayGrade, todayGrade, yesterdayVal, todayVal)
                    ));
                } else if (alertType == null) {
                    alerts.add(new ProsperityAlertDto.AlertEntry(
                            industry, "grade_up", "等級上升",
                            Math.round(yesterdayVal * 100.0) / 100.0,
                            Math.round(todayVal * 100.0) / 100.0,
                            Math.round(change * 100.0) / 100.0,
                            yesterdayGrade, todayGrade, "medium",
                            String.format("%s 等級從「%s」上升到「%s」",
                                    industry, yesterdayGrade, todayGrade)
                    ));
                }
            } else if (todayGradeLevel < yesterdayGradeLevel) {
                // 等級躍降
                if (yesterdayGradeLevel - todayGradeLevel >= 2) {
                    alerts.add(new ProsperityAlertDto.AlertEntry(
                            industry, "grade_down", "等級躍降",
                            Math.round(yesterdayVal * 100.0) / 100.0,
                            Math.round(todayVal * 100.0) / 100.0,
                            Math.round(change * 100.0) / 100.0,
                            yesterdayGrade, todayGrade, "high",
                            String.format("%s 等級從「%s」躍降到「%s」（景氣度 %.1f → %.1f）",
                                    industry, yesterdayGrade, todayGrade, yesterdayVal, todayVal)
                    ));
                } else if (alertType == null) {
                    alerts.add(new ProsperityAlertDto.AlertEntry(
                            industry, "grade_down", "等級下降",
                            Math.round(yesterdayVal * 100.0) / 100.0,
                            Math.round(todayVal * 100.0) / 100.0,
                            Math.round(change * 100.0) / 100.0,
                            yesterdayGrade, todayGrade, "medium",
                            String.format("%s 等級從「%s」下降到「%s」",
                                    industry, yesterdayGrade, todayGrade)
                    ));
                }
            }

            // 景氣度突變（未伴隨等級變化時單獨記錄）
            if (alertType != null && todayGradeLevel == yesterdayGradeLevel) {
                String message = alertType.equals("surge")
                        ? String.format("%s 景氣度突升 %.1f → %.1f（+%s）",
                                industry, yesterdayVal, todayVal, String.format("%.1f", change))
                        : String.format("%s 景氣度突降 %.1f → %.1f（%s）",
                                industry, yesterdayVal, todayVal, String.format("%.1f", change));
                alerts.add(new ProsperityAlertDto.AlertEntry(
                        industry, alertType, alertTypeName,
                        Math.round(yesterdayVal * 100.0) / 100.0,
                        Math.round(todayVal * 100.0) / 100.0,
                        Math.round(change * 100.0) / 100.0,
                        yesterdayGrade, todayGrade, severity, message
                ));
            }
        }

        // 按嚴重程度和變化幅度排序
        alerts.sort((a, b) -> {
            int sa = severityRank(a.severity());
            int sb = severityRank(b.severity());
            if (sa != sb) return sb - sa;
            return Double.compare(Math.abs(b.change()), Math.abs(a.change()));
        });

        String summary = String.format(
                "分析日期 %s（對比 %s → %s）：共檢測到 %d 條預警（%d 條高嚴重度）。",
                latestDate, prevDate, latestDate, alerts.size(),
                alerts.stream().filter(a -> "high".equals(a.severity())).count()
        );

        return new ProsperityAlertDto(latestDate.toString(), alerts, summary);
    }

    // ------------------------------------------------------------------------
    // 私有輔助方法
    // ------------------------------------------------------------------------

    /** 計算指定日期列表的景氣度 Map（industry -> prosperityIndex）。 */
    private Map<String, Double> computeProsperityMap(List<IndustryDailyEntity> entities) {
        if (entities == null || entities.isEmpty()) return Map.of();

        double[] pctArr = entities.stream()
                .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0)
                .toArray();
        double[] amtArr = entities.stream()
                .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                .toArray();
        double[] turnArr = entities.stream()
                .mapToDouble(e -> e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0)
                .toArray();

        double pctMin = StockMathUtils.min(pctArr), pctMax = StockMathUtils.max(pctArr);
        double amtMin = StockMathUtils.min(amtArr), amtMax = StockMathUtils.max(amtArr);
        double turnMin = StockMathUtils.min(turnArr), turnMax = StockMathUtils.max(turnArr);

        // 廣度：與 industryProsperity() 保持一致，使用 per-entity rising/(rising+falling)*100
        double[] breadthArr = entities.stream()
                .mapToDouble(e -> {
                    int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
                    int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
                    int total = rising + falling;
                    return total > 0 ? (double) rising / total * 100.0 : 50.0;
                })
                .toArray();
        double breadthMin = StockMathUtils.min(breadthArr), breadthMax = StockMathUtils.max(breadthArr);

        Map<String, Double> result = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            double pctChg = e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0.0;
            double amount = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
            double turn = e.getAvgTurn() != null ? e.getAvgTurn().doubleValue() : 0.0;
            int rising = e.getRisingCount() != null ? e.getRisingCount() : 0;
            int falling = e.getFallingCount() != null ? e.getFallingCount() : 0;
            int total = rising + falling;
            double breadth = total > 0 ? (double) rising / total * 100.0 : 50.0;

            double momentumScore = StockMathUtils.normalize(pctChg, pctMin, pctMax);
            double capitalScore = StockMathUtils.normalize(amount, amtMin, amtMax);
            double activityScore = StockMathUtils.normalize(turn, turnMin, turnMax);
            double breadthScore = StockMathUtils.normalize(breadth, breadthMin, breadthMax);

            double prosperityIndex = momentumScore * 0.35 + capitalScore * 0.25
                    + activityScore * 0.20 + breadthScore * 0.20;
            result.put(e.getIndustry(), prosperityIndex);
        }
        return result;
    }

    /** 嚴重程度排序值。 */
    private static int severityRank(String severity) {
        return switch (severity) {
            case "high" -> 3;
            case "medium" -> 2;
            case "low" -> 1;
            default -> 0;
        };
    }
}
