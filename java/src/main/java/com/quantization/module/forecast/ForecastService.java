package com.quantization.module.forecast;

import com.quantization.config.CacheConfig;
import com.quantization.config.properties.AppProperties;
import com.quantization.module.stock.IndustryDailyEntity;
import com.quantization.module.stock.IndustryDailyRepository;
import com.quantization.module.stock.StockMathUtils;
import com.quantization.module.stock.dto.ProsperityForecastBacktestDto;
import com.quantization.module.stock.dto.ProsperityForecastDto;
import com.quantization.module.stock.dto.ProsperityMarkovDto;
import com.quantization.module.stock.dto.ProsperitySeasonalityDto;
import com.quantization.module.stock.dto.RotationAutoMlDto;
import com.quantization.module.stock.dto.RotationBacktestDto;
import com.quantization.module.stock.dto.RotationMarkovDto;
import com.quantization.module.stock.dto.RotationPredictionDto;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 預測服務，封裝行業輪動預測、景氣度季節性分析、Markov 狀態轉移模型、
 * 多模型預測（ARIMA/Holt-Winters/線性回歸）及回測驗證等業務邏輯。
 */
@Service
@Transactional(readOnly = true)
public class ForecastService {

    /** Holt-Winters 季節週期（交易週=5 日）。如需調整（如月度數據用 21），改此常量。 */
    private static final int HW_SEASON_LENGTH = 5;

    /** 集成預測固定權重：ARIMA / Holt-Winters / 線性回歸。回測端點會計算最優權重供參考。 */
    private static final double W_ARIMA = 0.35;
    private static final double W_HW = 0.35;
    private static final double W_LR = 0.30;

    private final IndustryDailyRepository industryDailyRepository;
    private final AppProperties appProperties;

    public ForecastService(IndustryDailyRepository industryDailyRepository, AppProperties appProperties) {
        this.industryDailyRepository = industryDailyRepository;
        this.appProperties = appProperties;
    }

    /** 供 {@code @Cacheable} SpEL 引用的預測權重配置後綴，確保 fixed/adaptive 切換不命中彼此的緩存。 */
    public String forecastCacheKeySuffix() {
        AppProperties.Forecast f = appProperties.getForecast();
        return (f.isAdaptiveWeights() ? "adaptive" : "fixed") + "-" + f.getRollingWindowDays();
    }

    // ------------------------------------------------------------------------
    // 行業輪動預測
    // ------------------------------------------------------------------------

    /**
     * 行業輪動預測 — 基於歷史輪動規律預測下一輪領漲行業。
     *
     * 預測模型綜合三個維度：
     * 1. 動量延續（權重 0.40）：近期累計漲跌幅，強者恆強
     * 2. 資金流向（權重 0.35）：成交金額佔比變化，資金流入更可能領漲
     * 3. 景氣度趨勢（權重 0.25）：景氣度變化趨勢，上升者更可能領漲
     *
     * @param lookbackDays 回溯天數（用於計算歷史輪動規律）
     * @return 輪動預測 DTO
     */
    @Cacheable(value = CacheConfig.ROTATION_CACHE, key = "'rotation-prediction-' + #p0")
    public RotationPredictionDto predictRotation(int lookbackDays) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusDays(lookbackDays + 10);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new RotationPredictionDto(
                    end.toString(), lookbackDays + "日",
                    List.of(), List.of(), "數據不足，無法預測", 0.0
            );
        }

        // 按行業分組
        Map<String, List<IndustryDailyEntity>> byIndustry = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byIndustry.computeIfAbsent(e.getIndustry(), k -> new ArrayList<>()).add(e);
        }

        // 按日期分組（用於計算每日總成交額）
        Map<LocalDate, Double> dailyTotalAmount = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            double amt = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
            dailyTotalAmount.merge(e.getTradeDate(), amt, Double::sum);
        }

        List<LocalDate> sortedDates = new ArrayList<>(dailyTotalAmount.keySet());
        sortedDates.sort(LocalDate::compareTo);
        if (sortedDates.size() < 2) {
            return new RotationPredictionDto(
                    end.toString(), lookbackDays + "日",
                    List.of(), List.of(), "交易日不足，無法預測", 0.0
            );
        }

        LocalDate firstDate = sortedDates.get(0);
        LocalDate lastDate = sortedDates.get(sortedDates.size() - 1);
        double firstTotal = dailyTotalAmount.get(firstDate);
        double lastTotal = dailyTotalAmount.get(lastDate);

        // 計算每個行業的三個維度評分
        List<PredictionScore> scores = new ArrayList<>();
        for (Map.Entry<String, List<IndustryDailyEntity>> entry : byIndustry.entrySet()) {
            String industry = entry.getKey();
            List<IndustryDailyEntity> list = entry.getValue();
            if (list.size() < 2) continue;

            // 1. 動量：累計漲跌幅
            double momentum = 0.0;
            for (IndustryDailyEntity e : list) {
                if (e.getAvgPctChg() != null) {
                    momentum += e.getAvgPctChg().doubleValue();
                }
            }

            // 2. 資金流向：成交金額佔比變化
            double firstAmount = list.stream()
                    .filter(e -> e.getTradeDate().equals(firstDate))
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .findFirst().orElse(0.0);
            double lastAmount = list.stream()
                    .filter(e -> e.getTradeDate().equals(lastDate))
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .findFirst().orElse(0.0);
            double firstShare = firstTotal > 0 ? firstAmount / firstTotal : 0.0;
            double lastShare = lastTotal > 0 ? lastAmount / lastTotal : 0.0;
            double capitalFlow = (lastShare - firstShare) * 100.0; // 百分點變化

            // 3. 景氣度趨勢：近期漲跌幅趨勢（最後 5 日 vs 前 5 日）
            int midPoint = list.size() / 2;
            double firstHalfAvg = list.subList(0, Math.min(midPoint, list.size())).stream()
                    .filter(e -> e.getAvgPctChg() != null)
                    .mapToDouble(e -> e.getAvgPctChg().doubleValue())
                    .average().orElse(0.0);
            double lastHalfAvg = list.subList(midPoint, list.size()).stream()
                    .filter(e -> e.getAvgPctChg() != null)
                    .mapToDouble(e -> e.getAvgPctChg().doubleValue())
                    .average().orElse(0.0);
            double trendChange = lastHalfAvg - firstHalfAvg;

            scores.add(new PredictionScore(industry, momentum, capitalFlow, trendChange));
        }

        if (scores.isEmpty()) {
            return new RotationPredictionDto(
                    end.toString(), lookbackDays + "日",
                    List.of(), List.of(), "有效行業數不足，無法預測", 0.0
            );
        }

        // 標準化各維度到 0-100
        double momMin = scores.stream().mapToDouble(s -> s.momentum).min().orElse(0);
        double momMax = scores.stream().mapToDouble(s -> s.momentum).max().orElse(0);
        double capMin = scores.stream().mapToDouble(s -> s.capitalFlow).min().orElse(0);
        double capMax = scores.stream().mapToDouble(s -> s.capitalFlow).max().orElse(0);
        double trendMin = scores.stream().mapToDouble(s -> s.trendChange).min().orElse(0);
        double trendMax = scores.stream().mapToDouble(s -> s.trendChange).max().orElse(0);

        // 計算綜合評分
        List<RotationPredictionDto.PredictedIndustry> predictions = new ArrayList<>();
        for (PredictionScore s : scores) {
            double momScore = StockMathUtils.normalize(s.momentum, momMin, momMax);
            double capScore = StockMathUtils.normalize(s.capitalFlow, capMin, capMax);
            double trendScore = StockMathUtils.normalize(s.trendChange, trendMin, trendMax);

            double composite = momScore * 0.40 + capScore * 0.35 + trendScore * 0.25;

            String reason = String.format(
                    "動量%.1f(累計%.2f%%), 資金%.1f(佔比變化%.2f%%), 趨勢%.1f(後半段均漲%.3f%%)",
                    momScore, s.momentum, capScore, s.capitalFlow, trendScore, s.trendChange
            );

            predictions.add(new RotationPredictionDto.PredictedIndustry(
                    s.industry,
                    Math.round(composite * 100.0) / 100.0,
                    Math.round(momScore * 100.0) / 100.0,
                    Math.round(capScore * 100.0) / 100.0,
                    Math.round(trendScore * 100.0) / 100.0,
                    reason
            ));
        }

        // 按評分排序
        predictions.sort((a, b) -> Double.compare(b.score(), a.score()));

        // 取 Top 5 領漲和 Bottom 5 滯後
        List<RotationPredictionDto.PredictedIndustry> leaders = predictions.stream().limit(5).toList();
        List<RotationPredictionDto.PredictedIndustry> laggards = predictions.stream()
                .skip(Math.max(0, predictions.size() - 5))
                .toList();

        // 計算信心度（基於 Top 1 與中位數的差距）
        double topScore = leaders.isEmpty() ? 0 : leaders.get(0).score();
        double medianScore = predictions.size() > 0
                ? predictions.get(predictions.size() / 2).score()
                : 50.0;
        double confidence = Math.min(100.0, Math.max(0.0, (topScore - medianScore) * 2.0));

        // 構建預測理由
        String reasoning = String.format(
                "基於最近 %d 日數據，綜合動量(40%%)+資金流向(35%%)+景氣度趨勢(25%%)預測。" +
                "最可能領漲：%s（評分%.1f）。信心度%.1f%%。",
                lookbackDays,
                leaders.isEmpty() ? "無" : leaders.get(0).industry(),
                topScore,
                confidence
        );

        return new RotationPredictionDto(
                lastDate.toString(),
                lookbackDays + "日",
                leaders,
                laggards,
                reasoning,
                Math.round(confidence * 100.0) / 100.0
        );
    }

    /** 輪動預測內部評分數據。 */
    private record PredictionScore(String industry, double momentum, double capitalFlow, double trendChange) {
    }

    /**
     * 行業輪動預測回測 — 驗證歷史預測準確率。
     *
     * 回測邏輯：
     * 1. 取最近 backtestDays 的交易日列表
     * 2. 對每個交易日 T（排除最近 forwardDays 日，因為無法驗證）：
     *    - 用 T 之前 lookbackDays 的數據生成預測
     *    - 計算 T → T+forwardDays 內各行業實際累計漲跌幅
     *    - 檢查預測 Top 5 領漲是否在實際 Top 5 內（命中）
     *    - 計算預測領漲行業的平均收益 vs 市場平均收益（超額收益）
     * 3. 匯總命中率、平均超額收益
     *
     * @param lookbackDays  預測回溯天數
     * @param forwardDays   前瞻驗證天數
     * @param backtestDays  回測總天數
     * @return 回測結果 DTO
     */
    @Cacheable(value = CacheConfig.ROTATION_CACHE, key = "'rotation-backtest-' + #p0 + '-' + #p1 + '-' + #p2")
    public RotationBacktestDto backtestRotationPrediction(int lookbackDays, int forwardDays, int backtestDays) {
        LocalDate today = LocalDate.now();
        LocalDate dataStart = today.minusDays(lookbackDays + backtestDays + forwardDays + 20);
        LocalDate dataEnd = today;

        List<IndustryDailyEntity> allEntities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(dataStart, dataEnd);

        if (allEntities.isEmpty()) {
            return new RotationBacktestDto(lookbackDays, forwardDays, 0, 0, 0, 0, 0, 0,
                    "數據不足，無法回測", List.of());
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : allEntities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < lookbackDays + forwardDays + 5) {
            return new RotationBacktestDto(lookbackDays, forwardDays, 0, 0, 0, 0, 0, 0,
                    "交易日不足，無法回測（需要至少 " + (lookbackDays + forwardDays + 5) + " 個交易日）", List.of());
        }

        // 回測窗口：從第 lookbackDays 個交易日開始，到倒數 forwardDays 個交易日結束
        int startIdx = Math.max(lookbackDays, 5);
        int endIdx = sortedDates.size() - forwardDays;

        List<RotationBacktestDto.BacktestEntry> entries = new ArrayList<>();
        int hitCount = 0;
        double totalLeaderReturn = 0.0;
        double totalLaggardReturn = 0.0;
        double totalMarketReturn = 0.0;

        // 每隔幾個交易日取樣一次（避免過多回測點）
        int step = Math.max(1, (endIdx - startIdx) / 30); // 最多 30 個回測點

        for (int i = startIdx; i < endIdx; i += step) {
            LocalDate predictDate = sortedDates.get(i);
            LocalDate actualEndDate = sortedDates.get(Math.min(i + forwardDays, sortedDates.size() - 1));

            // 1. 用 predictDate 之前 lookbackDays 的數據生成預測
            int windowStart = Math.max(0, i - lookbackDays);
            List<IndustryDailyEntity> windowData = new ArrayList<>();
            for (int j = windowStart; j <= i; j++) {
                windowData.addAll(byDate.get(sortedDates.get(j)));
            }

            List<String> predictedTop5 = predictTopIndustries(windowData, 5);
            if (predictedTop5.isEmpty()) continue;

            // 2. 計算 predictDate → actualEndDate 內各行業實際累計漲跌幅
            Map<String, Double> actualReturns = new HashMap<>();
            for (int j = i + 1; j <= Math.min(i + forwardDays, sortedDates.size() - 1); j++) {
                for (IndustryDailyEntity e : byDate.get(sortedDates.get(j))) {
                    if (e.getAvgPctChg() != null) {
                        actualReturns.merge(e.getIndustry(), e.getAvgPctChg().doubleValue(), Double::sum);
                    }
                }
            }

            if (actualReturns.isEmpty()) continue;

            // 3. 找出實際 Top 5 行業
            List<String> actualTop5 = actualReturns.entrySet().stream()
                    .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                    .limit(5)
                    .map(Map.Entry::getKey)
                    .toList();

            String actualTop = actualTop5.isEmpty() ? "無" : actualTop5.get(0);

            // 4. 計算預測領漲行業的實際收益
            String topPredicted = predictedTop5.get(0);
            double predictedReturn = actualReturns.getOrDefault(topPredicted, 0.0);
            double marketAvg = actualReturns.values().stream()
                    .mapToDouble(Double::doubleValue).average().orElse(0.0);
            double excessReturn = predictedReturn - marketAvg;

            // 5. 命中判定：預測 Top 5 與實際 Top 5 有交集
            boolean hit = predictedTop5.stream().anyMatch(actualTop5::contains);
            if (hit) hitCount++;

            totalLeaderReturn += predictedReturn;
            totalMarketReturn += marketAvg;
            entries.add(new RotationBacktestDto.BacktestEntry(
                    predictDate.toString(),
                    topPredicted,
                    actualTop,
                    Math.round(predictedReturn * 1000.0) / 1000.0,
                    Math.round(marketAvg * 1000.0) / 1000.0,
                    Math.round(excessReturn * 1000.0) / 1000.0,
                    hit
            ));
        }

        int total = entries.size();
        double hitRate = total > 0 ? (double) hitCount / total * 100.0 : 0.0;
        double avgLeaderReturn = total > 0 ? totalLeaderReturn / total : 0.0;
        double avgMarketReturn = total > 0 ? totalMarketReturn / total : 0.0;
        double avgExcessReturn = avgLeaderReturn - avgMarketReturn;

        String summary = String.format(
                "回測 %d 次（lookback=%d日, forward=%d日）。命中率 %.1f%%。" +
                "預測領漲平均收益 %.3f%%，市場平均 %.3f%%，超額收益 %.3f%%。",
                total, lookbackDays, forwardDays, hitRate,
                avgLeaderReturn, avgMarketReturn, avgExcessReturn
        );

        return new RotationBacktestDto(
                lookbackDays, forwardDays, total, hitCount,
                Math.round(hitRate * 100.0) / 100.0,
                Math.round(avgLeaderReturn * 1000.0) / 1000.0,
                Math.round(avgMarketReturn * 1000.0) / 1000.0,
                Math.round(avgExcessReturn * 1000.0) / 1000.0,
                summary,
                entries
        );
    }

    /**
     * 日期隔離回測 — 僅在 [rangeStart, rangeEnd] 區間內運行回測，保證不接觸區間外的數據。
     *
     * 與 {@link #backtestRotationPrediction(int, int, int)} 的區別：
     * - 數據拉取範圍為 [rangeStart, rangeEnd + forwardDays 緩衝]，**不拉取 rangeStart 之前的數據**
     * - 預測日期 T 嚴格限制在 [rangeStart, rangeEnd] 內
     * - 回溯窗口 [T-lookback, T] 也嚴格在 [rangeStart, rangeEnd] 內（T 至少是區間內第 lookbackDays 個交易日）
     * - 前瞻驗證窗口 [T+1, T+forward] 可延伸到 rangeEnd 之後（已預留緩衝數據）
     *
     * 此方法用於 AutoML 的嚴格 out-of-sample 評估：調參區間 A 和評估區間 B 的數據完全不重疊。
     *
     * @param lookbackDays 回溯天數
     * @param forwardDays  前瞻驗證天數
     * @param rangeStart   回測區間起始日期（含）
     * @param rangeEnd     回測區間結束日期（含）
     * @return 回測結果 DTO
     */
    private RotationBacktestDto backtestRotationPredictionInRange(
            int lookbackDays, int forwardDays, LocalDate rangeStart, LocalDate rangeEnd) {
        // 數據拉取：從 rangeStart 起（不含之前數據），到 rangeEnd + forwardDays 緩衝（供前瞻驗證）
        LocalDate dataStart = rangeStart;
        LocalDate dataEnd = rangeEnd.plusDays(forwardDays + 20);

        List<IndustryDailyEntity> allEntities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(dataStart, dataEnd);

        if (allEntities.isEmpty()) {
            return new RotationBacktestDto(lookbackDays, forwardDays, 0, 0, 0, 0, 0, 0,
                    "數據不足，無法回測", List.of());
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : allEntities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < lookbackDays + forwardDays + 5) {
            return new RotationBacktestDto(lookbackDays, forwardDays, 0, 0, 0, 0, 0, 0,
                    "交易日不足，無法回測（需要至少 " + (lookbackDays + forwardDays + 5) + " 個交易日）", List.of());
        }

        // 預測日期窗口：從第 lookbackDays 個交易日開始（保證回溯窗口在區間內），
        // 到倒數 forwardDays 個交易日結束（保證前瞻驗證有足夠數據）
        int startIdx = Math.max(lookbackDays, 5);
        int endIdx = sortedDates.size() - forwardDays;

        List<RotationBacktestDto.BacktestEntry> entries = new ArrayList<>();
        int hitCount = 0;
        double totalLeaderReturn = 0.0;
        double totalMarketReturn = 0.0;

        // 每隔幾個交易日取樣一次（避免過多回測點）
        int step = Math.max(1, (endIdx - startIdx) / 30);

        for (int i = startIdx; i < endIdx; i += step) {
            LocalDate predictDate = sortedDates.get(i);

            // 1. 用 predictDate 之前 lookbackDays 的數據生成預測（窗口嚴格在區間內）
            int windowStart = Math.max(0, i - lookbackDays);
            List<IndustryDailyEntity> windowData = new ArrayList<>();
            for (int j = windowStart; j <= i; j++) {
                windowData.addAll(byDate.get(sortedDates.get(j)));
            }

            List<String> predictedTop5 = predictTopIndustries(windowData, 5);
            if (predictedTop5.isEmpty()) continue;

            // 2. 計算 predictDate → actualEndDate 內各行業實際累計漲跌幅
            Map<String, Double> actualReturns = new HashMap<>();
            for (int j = i + 1; j <= Math.min(i + forwardDays, sortedDates.size() - 1); j++) {
                for (IndustryDailyEntity e : byDate.get(sortedDates.get(j))) {
                    if (e.getAvgPctChg() != null) {
                        actualReturns.merge(e.getIndustry(), e.getAvgPctChg().doubleValue(), Double::sum);
                    }
                }
            }

            if (actualReturns.isEmpty()) continue;

            // 3. 找出實際 Top 5 行業
            List<String> actualTop5 = actualReturns.entrySet().stream()
                    .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                    .limit(5)
                    .map(Map.Entry::getKey)
                    .toList();

            String actualTop = actualTop5.isEmpty() ? "無" : actualTop5.get(0);

            // 4. 計算預測領漲行業的實際收益
            String topPredicted = predictedTop5.get(0);
            double predictedReturn = actualReturns.getOrDefault(topPredicted, 0.0);
            double marketAvg = actualReturns.values().stream()
                    .mapToDouble(Double::doubleValue).average().orElse(0.0);
            double excessReturn = predictedReturn - marketAvg;

            // 5. 命中判定：預測 Top 5 與實際 Top 5 有交集
            boolean hit = predictedTop5.stream().anyMatch(actualTop5::contains);
            if (hit) hitCount++;

            totalLeaderReturn += predictedReturn;
            totalMarketReturn += marketAvg;
            entries.add(new RotationBacktestDto.BacktestEntry(
                    predictDate.toString(),
                    topPredicted,
                    actualTop,
                    Math.round(predictedReturn * 1000.0) / 1000.0,
                    Math.round(marketAvg * 1000.0) / 1000.0,
                    Math.round(excessReturn * 1000.0) / 1000.0,
                    hit
            ));
        }

        int total = entries.size();
        double hitRate = total > 0 ? (double) hitCount / total * 100.0 : 0.0;
        double avgLeaderReturn = total > 0 ? totalLeaderReturn / total : 0.0;
        double avgMarketReturn = total > 0 ? totalMarketReturn / total : 0.0;
        double avgExcessReturn = avgLeaderReturn - avgMarketReturn;

        String summary = String.format(
                "回測 %d 次（lookback=%d日, forward=%d日, 區間=%s~%s）。命中率 %.1f%%。" +
                "預測領漲平均收益 %.3f%%，市場平均 %.3f%%，超額收益 %.3f%%。",
                total, lookbackDays, forwardDays, rangeStart, rangeEnd, hitRate,
                avgLeaderReturn, avgMarketReturn, avgExcessReturn
        );

        return new RotationBacktestDto(
                lookbackDays, forwardDays, total, hitCount,
                Math.round(hitRate * 100.0) / 100.0,
                Math.round(avgLeaderReturn * 1000.0) / 1000.0,
                Math.round(avgMarketReturn * 1000.0) / 1000.0,
                Math.round(avgExcessReturn * 1000.0) / 1000.0,
                summary,
                entries
        );
    }

    /**
     * 內部方法：用給定數據窗口預測 Top N 領漲行業。
     * 邏輯與 predictRotation 相同，但不依賴當前日期。
     */
    private List<String> predictTopIndustries(List<IndustryDailyEntity> windowData, int topN) {
        if (windowData == null || windowData.size() < 10) return List.of();

        // 按行業分組
        Map<String, List<IndustryDailyEntity>> byIndustry = new LinkedHashMap<>();
        for (IndustryDailyEntity e : windowData) {
            byIndustry.computeIfAbsent(e.getIndustry(), k -> new ArrayList<>()).add(e);
        }

        // 按日期分組計算每日總成交額
        Map<LocalDate, Double> dailyTotal = new LinkedHashMap<>();
        for (IndustryDailyEntity e : windowData) {
            double amt = e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0;
            dailyTotal.merge(e.getTradeDate(), amt, Double::sum);
        }

        List<LocalDate> dates = new ArrayList<>(dailyTotal.keySet());
        dates.sort(LocalDate::compareTo);
        if (dates.size() < 2) return List.of();

        LocalDate firstDate = dates.get(0);
        LocalDate lastDate = dates.get(dates.size() - 1);
        double firstTotal = dailyTotal.get(firstDate);
        double lastTotal = dailyTotal.get(lastDate);

        List<PredictionScore> scores = new ArrayList<>();
        for (Map.Entry<String, List<IndustryDailyEntity>> entry : byIndustry.entrySet()) {
            List<IndustryDailyEntity> list = entry.getValue();
            if (list.size() < 2) continue;

            double momentum = 0.0;
            for (IndustryDailyEntity e : list) {
                if (e.getAvgPctChg() != null) momentum += e.getAvgPctChg().doubleValue();
            }

            double firstAmount = list.stream()
                    .filter(e -> e.getTradeDate().equals(firstDate))
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .findFirst().orElse(0.0);
            double lastAmount = list.stream()
                    .filter(e -> e.getTradeDate().equals(lastDate))
                    .mapToDouble(e -> e.getTotalAmount() != null ? e.getTotalAmount().doubleValue() : 0.0)
                    .findFirst().orElse(0.0);
            double firstShare = firstTotal > 0 ? firstAmount / firstTotal : 0.0;
            double lastShare = lastTotal > 0 ? lastAmount / lastTotal : 0.0;
            double capitalFlow = (lastShare - firstShare) * 100.0;

            int midPoint = list.size() / 2;
            double firstHalfAvg = list.subList(0, Math.min(midPoint, list.size())).stream()
                    .filter(e -> e.getAvgPctChg() != null)
                    .mapToDouble(e -> e.getAvgPctChg().doubleValue())
                    .average().orElse(0.0);
            double lastHalfAvg = list.subList(midPoint, list.size()).stream()
                    .filter(e -> e.getAvgPctChg() != null)
                    .mapToDouble(e -> e.getAvgPctChg().doubleValue())
                    .average().orElse(0.0);
            double trendChange = lastHalfAvg - firstHalfAvg;

            scores.add(new PredictionScore(entry.getKey(), momentum, capitalFlow, trendChange));
        }

        if (scores.isEmpty()) return List.of();

        // 標準化
        double momMin = scores.stream().mapToDouble(s -> s.momentum).min().orElse(0);
        double momMax = scores.stream().mapToDouble(s -> s.momentum).max().orElse(0);
        double capMin = scores.stream().mapToDouble(s -> s.capitalFlow).min().orElse(0);
        double capMax = scores.stream().mapToDouble(s -> s.capitalFlow).max().orElse(0);
        double trendMin = scores.stream().mapToDouble(s -> s.trendChange).min().orElse(0);
        double trendMax = scores.stream().mapToDouble(s -> s.trendChange).max().orElse(0);

        // 計算綜合評分並排序
        List<Map.Entry<String, Double>> ranked = new ArrayList<>();
        for (PredictionScore s : scores) {
            double momScore = StockMathUtils.normalize(s.momentum, momMin, momMax);
            double capScore = StockMathUtils.normalize(s.capitalFlow, capMin, capMax);
            double trendScore = StockMathUtils.normalize(s.trendChange, trendMin, trendMax);
            double composite = momScore * 0.40 + capScore * 0.35 + trendScore * 0.25;
            ranked.add(Map.entry(s.industry, composite));
        }

        ranked.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));
        return ranked.stream().limit(topN).map(Map.Entry::getKey).toList();
    }

    /**
     * 輪動預測 AutoML 自動調參 — 自動尋找最佳 lookbackDays × forwardDays 組合。
     *
     * <p>採用<b>嚴格日期隔離 out-of-sample 評估設計</b>：
     * <ul>
     *   <li><b>調參階段（tune，區間 A）</b>：只用區間 A [tuneStartDate, tuneEndDate] 的數據
     *       做 15 組合網格搜索，選出綜合評分最高的參數組合。評估階段絕不接觸區間 A 的數據。</li>
     *   <li><b>評估階段（eval，區間 B）</b>：用選出的最佳參數在區間 B [evalStartDate, evalEndDate]
     *       上跑回測，報告 out-of-sample 表現。區間 B 在區間 A 之後，兩者完全不重疊。</li>
     *   <li><b>最終報告</b>：在區間 B 上的命中率與超額收益，即真正的樣本外表現。</li>
     * </ul>
     *
     * <p>若不傳日期參數（調用 {@link #autoTuneRotationPrediction(int)}），使用默認分割：
     * 以當前日期為終點、向前回溯 backtestDays 天為總區間，前 70% 為調參區間 A，後 30% 為評估區間 B。
     *
     * <p>搜尋空間：
     * <ul>
     *   <li>lookbackDays: [5, 10, 15, 20, 30]</li>
     *   <li>forwardDays: [3, 5, 10]</li>
     * </ul>
     * 共 15 組合。
     *
     * <p>評分公式：compositeScore = hitRate * 0.6 + excessReturnNormalized * 0.4（基於調參段指標）
     *
     * @param backtestDays 回測總天數（默認 90，用於計算默認分割區間）
     * @return AutoML 結果 DTO
     */
    @Cacheable(value = CacheConfig.ROTATION_CACHE, key = "'rotation-automl-' + #p0")
    public RotationAutoMlDto autoTuneRotationPrediction(int backtestDays) {
        // 默認分割：前 70% 調參，後 30% 評估
        LocalDate today = LocalDate.now();
        LocalDate totalStart = today.minusDays(backtestDays);
        LocalDate splitPoint = totalStart.plusDays((long) (backtestDays * 0.7));
        LocalDate tuneStart = totalStart;
        LocalDate tuneEnd = splitPoint;
        LocalDate evalStart = splitPoint.plusDays(1);
        LocalDate evalEnd = today;
        return autoTuneRotationPrediction(backtestDays, tuneStart, tuneEnd, evalStart, evalEnd);
    }

    /**
     * 輪動預測 AutoML 自動調參（嚴格日期隔離版）— 指定調參區間 A 和評估區間 B。
     *
     * <p>嚴格保證：
     * <ul>
     *   <li>調參只用區間 A [tuneStartDate, tuneEndDate] 的數據</li>
     *   <li>評估只用區間 B [evalStartDate, evalEndDate] 的數據</li>
     *   <li>區間 B 必須在區間 A 之後（evalStartDate &gt; tuneEndDate），兩者不重疊</li>
     *   <li>評估階段絕不接觸區間 A 的數據</li>
     * </ul>
     *
     * @param backtestDays  回測總天數（保留參數以兼容緩存鍵，實際區間由日期參數決定）
     * @param tuneStartDate 調參區間 A 起始日期（含），null 時用默認前 70%
     * @param tuneEndDate   調參區間 A 結束日期（含），null 時用默認
     * @param evalStartDate 評估區間 B 起始日期（含），null 時用默認後 30%
     * @param evalEndDate   評估區間 B 結束日期（含），null 時用默認
     * @return AutoML 結果 DTO，含 tuneRange 和 evalRange 字段標明兩個區間
     */
    public RotationAutoMlDto autoTuneRotationPrediction(int backtestDays,
                                                        LocalDate tuneStartDate, LocalDate tuneEndDate,
                                                        LocalDate evalStartDate, LocalDate evalEndDate) {
        // 若任一日期為 null，回退到默認 70/30 分割
        if (tuneStartDate == null || tuneEndDate == null || evalStartDate == null || evalEndDate == null) {
            LocalDate today = LocalDate.now();
            LocalDate totalStart = today.minusDays(backtestDays);
            LocalDate splitPoint = totalStart.plusDays((long) (backtestDays * 0.7));
            if (tuneStartDate == null) tuneStartDate = totalStart;
            if (tuneEndDate == null) tuneEndDate = splitPoint;
            if (evalStartDate == null) evalStartDate = splitPoint.plusDays(1);
            if (evalEndDate == null) evalEndDate = today;
        }

        // 驗證區間 B 在區間 A 之後（嚴格不重疊）
        if (!evalStartDate.isAfter(tuneEndDate)) {
            // 區間重疊時自動調整：將 evalStart 移到 tuneEnd 之後
            evalStartDate = tuneEndDate.plusDays(1);
        }

        String tuneRange = tuneStartDate + " ~ " + tuneEndDate;
        String evalRange = evalStartDate + " ~ " + evalEndDate;

        int[] lookbackOptions = {5, 10, 15, 20, 30};
        int[] forwardOptions = {3, 5, 10};

        // ===== 調參階段：只用區間 A 的數據做網格搜索 =====
        List<RotationAutoMlDto.ParamCombination> combinations = new ArrayList<>();

        for (int lookback : lookbackOptions) {
            for (int forward : forwardOptions) {
                RotationBacktestDto tuneBt = backtestRotationPredictionInRange(
                        lookback, forward, tuneStartDate, tuneEndDate);
                if (tuneBt.totalPredictions() == 0) {
                    combinations.add(new RotationAutoMlDto.ParamCombination(
                            lookback, forward, 0, 0, 0, 0, 0, 0, 0));
                    continue;
                }
                combinations.add(new RotationAutoMlDto.ParamCombination(
                        lookback, forward,
                        tuneBt.hitRate(), tuneBt.avgExcessReturn(), tuneBt.avgLeaderReturn(),
                        tuneBt.totalPredictions(), 0, // compositeScore 稍後計算
                        0, 0 // eval 段稍後只對最佳組合計算
                ));
            }
        }

        // 標準化超額收益到 0-100（用 tune 段指標擇優）
        double minExcess = combinations.stream().mapToDouble(c -> c.avgExcessReturn()).min().orElse(0);
        double maxExcess = combinations.stream().mapToDouble(c -> c.avgExcessReturn()).max().orElse(0);

        // 計算綜合評分（基於 tune 段）
        List<RotationAutoMlDto.ParamCombination> scored = new ArrayList<>();
        for (RotationAutoMlDto.ParamCombination c : combinations) {
            double excessNorm = StockMathUtils.normalize(c.avgExcessReturn(), minExcess, maxExcess);
            double composite = c.hitRate() * 0.6 + excessNorm * 0.4;
            scored.add(new RotationAutoMlDto.ParamCombination(
                    c.lookbackDays(), c.forwardDays(),
                    c.hitRate(), c.avgExcessReturn(), c.avgLeaderReturn(),
                    c.totalPredictions(),
                    Math.round(composite * 100.0) / 100.0,
                    c.evalHitRate(), c.evalExcessReturn()
            ));
        }

        // 按 tune 段綜合評分排序，選出最佳參數
        scored.sort((a, b) -> Double.compare(b.compositeScore(), a.compositeScore()));
        RotationAutoMlDto.ParamCombination best = scored.isEmpty() ? null : scored.get(0);

        // ===== 評估階段：只用區間 B 的數據，用最佳參數跑回測 =====
        double evalHitRate = 0.0;
        double evalExcessReturn = 0.0;
        if (best != null && best.totalPredictions() > 0) {
            RotationBacktestDto evalBt = backtestRotationPredictionInRange(
                    best.lookbackDays(), best.forwardDays(), evalStartDate, evalEndDate);
            evalHitRate = evalBt.hitRate();
            evalExcessReturn = evalBt.avgExcessReturn();

            // 將最佳組合的 eval 結果填入
            int bestIdx = scored.indexOf(best);
            scored.set(bestIdx, new RotationAutoMlDto.ParamCombination(
                    best.lookbackDays(), best.forwardDays(),
                    best.hitRate(), best.avgExcessReturn(), best.avgLeaderReturn(),
                    best.totalPredictions(), best.compositeScore(),
                    evalHitRate, evalExcessReturn
            ));
        }

        String summary = best == null
                ? "數據不足，無法調參"
                : String.format(
                        "最佳參數：lookback=%d日, forward=%d日。調參區間(%s)命中率 %.1f%%，超額 %.3f%%；" +
                        "評估區間(%s)命中率 %.1f%%，超額 %.3f%%（嚴格 out-of-sample，區間不重疊）。",
                        best.lookbackDays(), best.forwardDays(),
                        tuneRange, best.hitRate(), best.avgExcessReturn(),
                        evalRange, evalHitRate, evalExcessReturn
                );

        return new RotationAutoMlDto(
                best == null ? 0 : best.lookbackDays(),
                best == null ? 0 : best.forwardDays(),
                best == null ? 0 : best.hitRate(),
                best == null ? 0 : best.avgExcessReturn(),
                best == null ? 0 : best.compositeScore(),
                summary,
                scored,
                tuneRange,
                evalRange
        );
    }

    // ------------------------------------------------------------------------
    // 行業景氣度週期性分析
    // ------------------------------------------------------------------------

    /**
     * 行業景氣度週期性分析 — 檢測季節性模式與週期規律。
     *
     * 分析維度：
     * 1. 月度模式：各行業在每個月的平均景氣度（1-12月）
     * 2. 星期模式：各行業在每個星期的平均景氣度（週一至週五）
     * 3. 季節性強度：月度方差 / 總方差（0-1，越高季節性越明顯）
     * 4. 最佳/最差月份
     *
     * @param months 分析回溯月數（默認 12）
     * @return 週期性分析 DTO
     */
    @Cacheable(value = CacheConfig.FORECAST_CACHE, key = "'prosperity-seasonality-' + #p0")
    public ProsperitySeasonalityDto prosperitySeasonality(int months) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusMonths(months);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new ProsperitySeasonalityDto(
                    start + " ~ " + end, 0, Map.of(), "數據不足，無法分析週期性");
        }

        // 按行業分組
        Map<String, List<IndustryDailyEntity>> byIndustry = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byIndustry.computeIfAbsent(e.getIndustry(), k -> new ArrayList<>()).add(e);
        }

        // 按日期分組（用於計算每日景氣度）
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        // 預計算每個交易日的景氣度 Map
        Map<LocalDate, Map<String, Double>> dailyProsperity = new LinkedHashMap<>();
        for (Map.Entry<LocalDate, List<IndustryDailyEntity>> entry : byDate.entrySet()) {
            dailyProsperity.put(entry.getKey(), computeProsperityMap(entry.getValue()));
        }

        Map<String, ProsperitySeasonalityDto.MonthlyPattern> industryPatterns = new LinkedHashMap<>();

        for (String industry : byIndustry.keySet()) {
            // 收集該行業所有交易日的景氣度
            List<double[]> monthValues = new ArrayList<>(); // [month, prosperity]
            List<double[]> weekdayValues = new ArrayList<>(); // [weekday, prosperity]
            List<Double> allValues = new ArrayList<>();

            for (Map.Entry<LocalDate, Map<String, Double>> dp : dailyProsperity.entrySet()) {
                Double val = dp.getValue().get(industry);
                if (val == null) continue;

                int month = dp.getKey().getMonthValue();
                int weekday = dp.getKey().getDayOfWeek().getValue(); // 1=Monday, 7=Sunday

                monthValues.add(new double[]{month, val});
                weekdayValues.add(new double[]{weekday, val});
                allValues.add(val);
            }

            if (allValues.isEmpty()) continue;

            // 計算月度平均
            Map<Integer, Double> monthlyAvg = new LinkedHashMap<>();
            Map<Integer, List<Double>> monthlyBuckets = new LinkedHashMap<>();
            for (double[] mv : monthValues) {
                int m = (int) mv[0];
                monthlyBuckets.computeIfAbsent(m, k -> new ArrayList<>()).add(mv[1]);
            }
            for (Map.Entry<Integer, List<Double>> me : monthlyBuckets.entrySet()) {
                double avg = me.getValue().stream().mapToDouble(Double::doubleValue).average().orElse(0);
                monthlyAvg.put(me.getKey(), Math.round(avg * 100.0) / 100.0);
            }

            // 計算星期平均
            Map<Integer, Double> weekdayAvg = new LinkedHashMap<>();
            Map<Integer, List<Double>> weekdayBuckets = new LinkedHashMap<>();
            for (double[] wv : weekdayValues) {
                int w = (int) wv[0];
                if (w <= 5) { // 只取週一至週五
                    weekdayBuckets.computeIfAbsent(w, k -> new ArrayList<>()).add(wv[1]);
                }
            }
            for (Map.Entry<Integer, List<Double>> we : weekdayBuckets.entrySet()) {
                double avg = we.getValue().stream().mapToDouble(Double::doubleValue).average().orElse(0);
                weekdayAvg.put(we.getKey(), Math.round(avg * 100.0) / 100.0);
            }

            // 找最佳/最差月份
            int bestMonth = 1, worstMonth = 1;
            double bestAvg = -1, worstAvg = 999;
            for (Map.Entry<Integer, Double> me : monthlyAvg.entrySet()) {
                if (me.getValue() > bestAvg) {
                    bestAvg = me.getValue();
                    bestMonth = me.getKey();
                }
                if (me.getValue() < worstAvg) {
                    worstAvg = me.getValue();
                    worstMonth = me.getKey();
                }
            }

            // 計算季節性強度（月度方差 / 總方差）
            double overallAvg = allValues.stream().mapToDouble(Double::doubleValue).average().orElse(0);
            double totalVariance = allValues.stream()
                    .mapToDouble(v -> Math.pow(v - overallAvg, 2)).sum() / allValues.size();
            double monthlyVariance = 0;
            for (Map.Entry<Integer, List<Double>> me : monthlyBuckets.entrySet()) {
                double mAvg = me.getValue().stream().mapToDouble(Double::doubleValue).average().orElse(0);
                monthlyVariance += me.getValue().size() * Math.pow(mAvg - overallAvg, 2);
            }
            monthlyVariance /= allValues.size();
            double seasonalityStrength = totalVariance > 0 ? monthlyVariance / totalVariance : 0;
            seasonalityStrength = Math.min(1.0, Math.max(0.0, seasonalityStrength));

            industryPatterns.put(industry, new ProsperitySeasonalityDto.MonthlyPattern(
                    industry,
                    monthlyAvg,
                    weekdayAvg,
                    bestMonth, worstMonth,
                    Math.round(bestAvg * 100.0) / 100.0,
                    Math.round(worstAvg * 100.0) / 100.0,
                    Math.round(seasonalityStrength * 1000.0) / 1000.0,
                    Math.round(overallAvg * 100.0) / 100.0
            ));
        }

        // 找出季節性最強的行業
        List<Map.Entry<String, ProsperitySeasonalityDto.MonthlyPattern>> sortedBySeasonality =
                new ArrayList<>(industryPatterns.entrySet());
        sortedBySeasonality.sort((a, b) -> Double.compare(
                b.getValue().seasonalityStrength(), a.getValue().seasonalityStrength()));

        String summary = String.format(
                "分析區間 %s ~ %s，共 %d 個數據點，%d 個行業。" +
                "季節性最強：%s（強度 %.2f，最佳月份 %d月，最差月份 %d月）。",
                start, end, entities.size(), industryPatterns.size(),
                sortedBySeasonality.isEmpty() ? "無" : sortedBySeasonality.get(0).getKey(),
                sortedBySeasonality.isEmpty() ? 0 : sortedBySeasonality.get(0).getValue().seasonalityStrength(),
                sortedBySeasonality.isEmpty() ? 0 : sortedBySeasonality.get(0).getValue().bestMonth(),
                sortedBySeasonality.isEmpty() ? 0 : sortedBySeasonality.get(0).getValue().worstMonth()
        );

        return new ProsperitySeasonalityDto(
                start + " ~ " + end,
                entities.size(),
                industryPatterns,
                summary
        );
    }

    // ------------------------------------------------------------------------
    // 行業景氣度 Markov 狀態轉移模型
    // ------------------------------------------------------------------------

    /**
     * 行業景氣度 Markov 狀態轉移模型 — 預測等級轉換概率。
     *
     * 將景氣度分為 5 個狀態：1=衰退, 2=低迷, 3=平穩, 4=景氣, 5=繁榮
     * 基於歷史等級轉換構建一階 Markov 轉移矩陣。
     *
     * @param months 分析回溯月數（默認 12）
     * @return Markov 分析 DTO
     */
    @Cacheable(value = CacheConfig.FORECAST_CACHE, key = "'prosperity-markov-' + #p0")
    public ProsperityMarkovDto prosperityMarkov(int months) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusMonths(months);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new ProsperityMarkovDto(end.toString(), 0, Map.of(), "數據不足，無法構建 Markov 模型");
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < 3) {
            return new ProsperityMarkovDto(end.toString(), 0, Map.of(), "交易日不足，無法構建 Markov 模型");
        }

        // 預計算每個交易日的景氣度 Map
        Map<LocalDate, Map<String, Double>> dailyProsperity = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            dailyProsperity.put(date, computeProsperityMap(byDate.get(date)));
        }

        // 按行業收集每日景氣度序列
        Map<String, List<LocalDate>> industryDates = new LinkedHashMap<>();
        Map<String, List<Double>> industrySeries = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            Map<String, Double> dp = dailyProsperity.get(date);
            for (Map.Entry<String, Double> e : dp.entrySet()) {
                industryDates.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(date);
                industrySeries.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(e.getValue());
            }
        }

        Map<String, ProsperityMarkovDto.IndustryMarkov> result = new LinkedHashMap<>();
        int totalTransitions = 0;

        for (String industry : industrySeries.keySet()) {
            List<Double> series = industrySeries.get(industry);
            if (series.size() < 3) continue;

            // 將景氣度轉為等級序列
            int[] gradeSeries = new int[series.size()];
            for (int i = 0; i < series.size(); i++) {
                gradeSeries[i] = StockMathUtils.gradeLevel(StockMathUtils.prosperityGrade(series.get(i)));
            }

            // 構建 5x5 轉移計數矩陣
            int[][] counts = new int[5][5];
            for (int i = 0; i < gradeSeries.length - 1; i++) {
                int from = gradeSeries[i] - 1; // 0-indexed
                int to = gradeSeries[i + 1] - 1;
                if (from >= 0 && from < 5 && to >= 0 && to < 5) {
                    counts[from][to]++;
                    totalTransitions++;
                }
            }

            // 轉為概率矩陣
            double[][] matrix = new double[5][5];
            for (int i = 0; i < 5; i++) {
                int rowSum = 0;
                for (int j = 0; j < 5; j++) rowSum += counts[i][j];
                for (int j = 0; j < 5; j++) {
                    matrix[i][j] = rowSum > 0 ? (double) counts[i][j] / rowSum : 0.0;
                    matrix[i][j] = Math.round(matrix[i][j] * 10000.0) / 10000.0;
                }
                // 若該行全零（無數據），設為均勻分布
                if (rowSum == 0) {
                    for (int j = 0; j < 5; j++) matrix[i][j] = 0.2;
                }
            }

            // 當前等級
            int currentState = gradeSeries[gradeSeries.length - 1];
            String currentStateName = gradeName(currentState);

            // 下一日各等級概率
            Map<Integer, Double> nextProb = new LinkedHashMap<>();
            int currentIdx = currentState - 1;
            for (int j = 0; j < 5; j++) {
                nextProb.put(j + 1, matrix[currentIdx][j]);
            }

            // 找最可能的下一等級
            int mostLikelyNext = 1;
            double mostLikelyProb = 0;
            for (int j = 0; j < 5; j++) {
                if (matrix[currentIdx][j] > mostLikelyProb) {
                    mostLikelyProb = matrix[currentIdx][j];
                    mostLikelyNext = j + 1;
                }
            }

            // 計算穩態分布（迭代法：P^n 收斂）
            Map<Integer, Double> steadyState = computeSteadyState(matrix);

            int transitionCount = 0;
            for (int i = 0; i < 5; i++) {
                for (int j = 0; j < 5; j++) transitionCount += counts[i][j];
            }

            result.put(industry, new ProsperityMarkovDto.IndustryMarkov(
                    industry,
                    matrix,
                    currentState,
                    currentStateName,
                    nextProb,
                    steadyState,
                    transitionCount,
                    gradeName(mostLikelyNext),
                    Math.round(mostLikelyProb * 1000.0) / 1000.0
            ));
        }

        String summary = String.format(
                "分析區間 %s ~ %s，共 %d 次等級轉換，%d 個行業。",
                start, end, totalTransitions, result.size()
        );

        return new ProsperityMarkovDto(end.toString(), totalTransitions, result, summary);
    }

    // ------------------------------------------------------------------------
    // 行業景氣度多模型預測
    // ------------------------------------------------------------------------

    /**
     * 行業景氣度多模型預測 — 整合 ARIMA、Holt-Winters、線性回歸。
     *
     * 三個模型均為純 Java 實作，CPU 秒級運算：
     * 1. ARIMA：簡化版 AR(2) + 一階差分
     * 2. Holt-Winters：三重指數平滑
     * 3. 線性回歸：OLS 趨勢預測
     *
     * <p>集成權重來源由 {@code app.forecast.adaptive-weights} 配置決定：
     * <ul>
     *   <li>{@code false}（默認）：固定權重 W_ARIMA/W_HW/W_LR，行為與 Phase 4 一致。</li>
     *   <li>{@code true}：調用 {@link #computeAdaptiveWeights} 用滾動窗口逆 MAE 計算動態權重，
     *       僅使用截至預測日的歷史數據，避免 look-ahead bias。</li>
     * </ul>
     *
     * @param months        分析回溯月數（默認 6）
     * @param forecastDays  預測天數（默認 5）
     * @return 多模型預測 DTO
     */
    @Cacheable(value = CacheConfig.FORECAST_CACHE,
            key = "'prosperity-forecast-' + #p0 + '-' + #p1 + '-' + #root.target.forecastCacheKeySuffix()")
    public ProsperityForecastDto prosperityForecast(int months, int forecastDays) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusMonths(months);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new ProsperityForecastDto(end.toString(), forecastDays, Map.of(), "數據不足，無法預測", weightSourceLabel());
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < 10) {
            return new ProsperityForecastDto(end.toString(), forecastDays, Map.of(), "交易日不足，無法預測（需至少 10 日）", weightSourceLabel());
        }

        // 預計算每日景氣度
        Map<LocalDate, Map<String, Double>> dailyProsperity = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            dailyProsperity.put(date, computeProsperityMap(byDate.get(date)));
        }

        // 按行業收集序列
        Map<String, List<Double>> industrySeries = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            Map<String, Double> dp = dailyProsperity.get(date);
            for (Map.Entry<String, Double> e : dp.entrySet()) {
                industrySeries.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(e.getValue());
            }
        }

        // 生成預測日期（跳過週末）
        List<String> forecastDates = new ArrayList<>();
        LocalDate forecastDate = sortedDates.get(sortedDates.size() - 1);
        int added = 0;
        while (added < forecastDays) {
            forecastDate = forecastDate.plusDays(1);
            int dow = forecastDate.getDayOfWeek().getValue();
            if (dow <= 5) {
                forecastDates.add(forecastDate.toString());
                added++;
            }
        }

        boolean adaptive = appProperties.getForecast().isAdaptiveWeights();
        int windowDays = appProperties.getForecast().getRollingWindowDays();
        String weightSource = weightSourceLabel();

        Map<String, ProsperityForecastDto.IndustryForecast> result = new LinkedHashMap<>();

        for (Map.Entry<String, List<Double>> entry : industrySeries.entrySet()) {
            String industry = entry.getKey();
            List<Double> series = entry.getValue();
            if (series.size() < 10) continue;

            double[] data = series.stream().mapToDouble(Double::doubleValue).toArray();

            // 1. ARIMA 預測（簡化版 AR(2) + 一階差分）
            double[] arimaForecast = forecastARIMA(data, forecastDays);

            // 2. Holt-Winters 預測（三重指數平滑，季節週期=HW_SEASON_LENGTH）
            double[] hwForecast = forecastHoltWinters(data, forecastDays, HW_SEASON_LENGTH);

            // 3. 線性回歸預測
            double[] linearForecast = forecastLinearRegression(data, forecastDays);

            // 4. 整合預測（權重來源：固定 or 滾動窗口逆 MAE 動態權重）
            double[] weights = adaptive
                    ? computeAdaptiveWeights(data, windowDays)
                    : new double[]{W_ARIMA, W_HW, W_LR};
            double wArima = weights[0];
            double wHw = weights[1];
            double wLinear = weights[2];
            double[] ensemble = new double[forecastDays];
            for (int i = 0; i < forecastDays; i++) {
                ensemble[i] = arimaForecast[i] * wArima + hwForecast[i] * wHw + linearForecast[i] * wLinear;
                ensemble[i] = Math.max(0, Math.min(100, ensemble[i]));
            }

            // 趨勢判斷
            double currentVal = data[data.length - 1];
            String arimaTrend = judgeTrend(currentVal, arimaForecast[arimaForecast.length - 1]);
            String hwTrend = judgeTrend(currentVal, hwForecast[hwForecast.length - 1]);
            String linearTrend = judgeTrend(currentVal, linearForecast[linearForecast.length - 1]);
            String consensusTrend = consensusTrend(arimaTrend, hwTrend, linearTrend);

            result.put(industry, new ProsperityForecastDto.IndustryForecast(
                    industry,
                    toList(arimaForecast),
                    toList(hwForecast),
                    toList(linearForecast),
                    toList(ensemble),
                    Math.round(currentVal * 100.0) / 100.0,
                    arimaTrend,
                    hwTrend,
                    linearTrend,
                    consensusTrend,
                    forecastDates,
                    Math.round(wArima * 10000.0) / 10000.0,
                    Math.round(wHw * 10000.0) / 10000.0,
                    Math.round(wLinear * 10000.0) / 10000.0
            ));
        }

        // 找共識上升最多的行業
        List<Map.Entry<String, ProsperityForecastDto.IndustryForecast>> sorted = new ArrayList<>(result.entrySet());
        sorted.sort((a, b) -> {
            double aDelta = a.getValue().ensembleForecast().get(forecastDays - 1) - a.getValue().currentProsperity();
            double bDelta = b.getValue().ensembleForecast().get(forecastDays - 1) - b.getValue().currentProsperity();
            return Double.compare(bDelta, aDelta);
        });

        String summary = String.format(
                "分析區間 %s ~ %s，預測未來 %d 日，%d 個行業。" +
                "共識上升最強：%s（%s）。共識下降最強：%s（%s）。",
                start, end, forecastDays, result.size(),
                sorted.isEmpty() ? "無" : sorted.get(0).getKey(),
                sorted.isEmpty() ? "" : sorted.get(0).getValue().consensusTrend(),
                sorted.isEmpty() ? "無" : sorted.get(sorted.size() - 1).getKey(),
                sorted.isEmpty() ? "" : sorted.get(sorted.size() - 1).getValue().consensusTrend()
        );

        return new ProsperityForecastDto(end.toString(), forecastDays, result, summary, weightSource);
    }

    /**
     * 行業景氣度預測回測 — 驗證多模型預測的歷史準確率。
     *
     * 回測邏輯：
     * 1. 對每個歷史交易日 T，用 T 之前的數據預測 T+forecastDays 的景氣度
     * 2. 比較預測值與實際景氣度
     * 3. 計算 MAE、方向準確率、等級命中率、超額收益
     *
     * @param months        分析回溯月數（默認 6）
     * @param forecastDays  預測天數（默認 5）
     * @param backtestDays  回測總天數（默認 60）
     * @return 回測結果 DTO
     */
    @Cacheable(value = CacheConfig.FORECAST_CACHE, key = "'forecast-backtest-' + #p0 + '-' + #p1 + '-' + #p2")
    public ProsperityForecastBacktestDto prosperityForecastBacktest(int months, int forecastDays, int backtestDays) {
        LocalDate today = LocalDate.now();
        LocalDate dataStart = today.minusMonths(months).minusDays(backtestDays + 20);
        LocalDate dataEnd = today;

        List<IndustryDailyEntity> allEntities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(dataStart, dataEnd);

        if (allEntities.isEmpty()) {
            return new ProsperityForecastBacktestDto(forecastDays, 0, 0, 0, 0, 0, 0, 0,
                    "數據不足，無法回測", List.of(), 0, 0, 0, "");
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : allEntities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < forecastDays + 10) {
            return new ProsperityForecastBacktestDto(forecastDays, 0, 0, 0, 0, 0, 0, 0,
                    "交易日不足，無法回測", List.of(), 0, 0, 0, "");
        }

        // 預計算每日景氣度
        Map<LocalDate, Map<String, Double>> dailyProsperity = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            dailyProsperity.put(date, computeProsperityMap(byDate.get(date)));
        }

        // 回測窗口
        int startIdx = Math.max(20, sortedDates.size() - backtestDays - forecastDays);
        int endIdx = sortedDates.size() - forecastDays;

        List<ProsperityForecastBacktestDto.BacktestEntry> entries = new ArrayList<>();
        double totalAbsError = 0;
        int directionCorrect = 0;
        int gradeCorrect = 0;
        double totalTopReturn = 0;
        double totalMarketReturn = 0;
        // P4-3: 追蹤各模型單獨 MAE 以計算最優權重
        double totalArimaError = 0;
        double totalHwError = 0;
        double totalLinearError = 0;

        // 每隔幾個交易日取樣一次
        int step = Math.max(1, (endIdx - startIdx) / 20);

        for (int i = startIdx; i < endIdx; i += step) {
            LocalDate predictDate = sortedDates.get(i);
            LocalDate targetDate = sortedDates.get(Math.min(i + forecastDays, sortedDates.size() - 1));

            // 用 predictDate 之前的數據預測
            Map<String, List<Double>> industrySeries = new LinkedHashMap<>();
            for (int j = Math.max(0, i - months * 21); j <= i; j++) {
                Map<String, Double> dp = dailyProsperity.get(sortedDates.get(j));
                for (Map.Entry<String, Double> e : dp.entrySet()) {
                    industrySeries.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(e.getValue());
                }
            }

            // 對每個行業預測景氣度（同時追蹤各模型單獨預測值以計算 per-model MAE）
            Map<String, Double> predictedProsperity = new LinkedHashMap<>();
            Map<String, double[]> perModelArima = new LinkedHashMap<>();
            Map<String, double[]> perModelHw = new LinkedHashMap<>();
            Map<String, double[]> perModelLinear = new LinkedHashMap<>();
            for (Map.Entry<String, List<Double>> entry : industrySeries.entrySet()) {
                double[] data = entry.getValue().stream().mapToDouble(Double::doubleValue).toArray();
                if (data.length < 10) continue;

                double[] arimaF = forecastARIMA(data, forecastDays);
                double[] hwF = forecastHoltWinters(data, forecastDays, HW_SEASON_LENGTH);
                double[] linearF = forecastLinearRegression(data, forecastDays);

                perModelArima.put(entry.getKey(), arimaF);
                perModelHw.put(entry.getKey(), hwF);
                perModelLinear.put(entry.getKey(), linearF);

                double ensemble = arimaF[arimaF.length - 1] * W_ARIMA
                        + hwF[hwF.length - 1] * W_HW + linearF[linearF.length - 1] * W_LR;
                predictedProsperity.put(entry.getKey(), Math.max(0, Math.min(100, ensemble)));
            }

            if (predictedProsperity.isEmpty()) continue;

            // 實際景氣度
            Map<String, Double> actualProsperity = dailyProsperity.getOrDefault(targetDate, Map.of());
            if (actualProsperity.isEmpty()) continue;

            // 找預測 Top 1 和實際 Top 1
            String topPredicted = predictedProsperity.entrySet().stream()
                    .max(Map.Entry.comparingByValue()).map(Map.Entry::getKey).orElse("");
            String topActual = actualProsperity.entrySet().stream()
                    .max(Map.Entry.comparingByValue()).map(Map.Entry::getKey).orElse("");

            double predictedVal = predictedProsperity.getOrDefault(topPredicted, 0.0);
            double actualVal = actualProsperity.getOrDefault(topPredicted, 0.0);
            double absError = Math.abs(predictedVal - actualVal);

            // 方向準確率：預測的上升/下降方向是否正確
            double prevVal = dailyProsperity.get(predictDate).getOrDefault(topPredicted, 50.0);
            boolean predictedUp = predictedVal > prevVal;
            boolean actualUp = actualVal > prevVal;
            boolean dirCorrect = predictedUp == actualUp;
            if (dirCorrect) directionCorrect++;

            // 等級命中率
            String predictedGrade = StockMathUtils.prosperityGrade(predictedVal);
            String actualGrade = StockMathUtils.prosperityGrade(actualVal);
            boolean gCorrect = predictedGrade.equals(actualGrade);
            if (gCorrect) gradeCorrect++;

            totalAbsError += absError;

            // P4-3: 追蹤各模型單獨預測的絕對誤差
            double[] arimaPred = perModelArima.getOrDefault(topPredicted, new double[]{50.0});
            double[] hwPred = perModelHw.getOrDefault(topPredicted, new double[]{50.0});
            double[] linearPred = perModelLinear.getOrDefault(topPredicted, new double[]{50.0});
            totalArimaError += Math.abs(arimaPred[arimaPred.length - 1] - actualVal);
            totalHwError += Math.abs(hwPred[hwPred.length - 1] - actualVal);
            totalLinearError += Math.abs(linearPred[linearPred.length - 1] - actualVal);

            // 超額收益：預測 Top 行業在 predictDate → targetDate 的實際漲跌幅
            double topReturn = 0;
            List<IndustryDailyEntity> predictDayEntities = byDate.get(predictDate);
            List<IndustryDailyEntity> targetDayEntities = byDate.get(targetDate);
            if (predictDayEntities != null && targetDayEntities != null) {
                double predictPct = predictDayEntities.stream()
                        .filter(e -> topPredicted.equals(e.getIndustry()))
                        .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0)
                        .findFirst().orElse(0);
                double targetPct = targetDayEntities.stream()
                        .filter(e -> topPredicted.equals(e.getIndustry()))
                        .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0)
                        .findFirst().orElse(0);
                topReturn = targetPct - predictPct;

                double marketPct = predictDayEntities.stream()
                        .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0)
                        .average().orElse(0);
                double marketTargetPct = targetDayEntities.stream()
                        .mapToDouble(e -> e.getAvgPctChg() != null ? e.getAvgPctChg().doubleValue() : 0)
                        .average().orElse(0);
                double marketReturn = marketTargetPct - marketPct;
                totalMarketReturn += marketReturn;
            }
            totalTopReturn += topReturn;

            entries.add(new ProsperityForecastBacktestDto.BacktestEntry(
                    predictDate.toString(),
                    targetDate.toString(),
                    topPredicted,
                    topActual,
                    Math.round(predictedVal * 100.0) / 100.0,
                    Math.round(actualVal * 100.0) / 100.0,
                    Math.round(absError * 100.0) / 100.0,
                    dirCorrect,
                    gCorrect
            ));
        }

        int total = entries.size();
        double mae = total > 0 ? totalAbsError / total : 0;
        double dirAcc = total > 0 ? (double) directionCorrect / total * 100.0 : 0;
        double gradeHit = total > 0 ? (double) gradeCorrect / total * 100.0 : 0;
        double avgTop = total > 0 ? totalTopReturn / total : 0;
        double avgMarket = total > 0 ? totalMarketReturn / total : 0;
        double avgExcess = avgTop - avgMarket;

        // P4-3: 各模型單獨 MAE + 逆 MAE 最優權重
        double arimaMae = total > 0 ? totalArimaError / total : 0;
        double hwMae = total > 0 ? totalHwError / total : 0;
        double linearMae = total > 0 ? totalLinearError / total : 0;
        String optimalWeights = computeOptimalWeights(arimaMae, hwMae, linearMae);

        String summary = String.format(
                "回測 %d 次（forecast=%d日）。整合 MAE %.2f，方向準確率 %.1f%%，等級命中率 %.1f%%。" +
                "預測 Top 行業平均收益 %.3f%%，市場平均 %.3f%%，超額收益 %.3f%%。" +
                "各模型 MAE — ARIMA %.2f / HW %.2f / LR %.2f。最優逆MAE權重：%s（當前固定權重 %.2f/%.2f/%.2f）。",
                total, forecastDays, mae, dirAcc, gradeHit, avgTop, avgMarket, avgExcess,
                arimaMae, hwMae, linearMae, optimalWeights, W_ARIMA, W_HW, W_LR
        );

        return new ProsperityForecastBacktestDto(
                forecastDays, total,
                Math.round(mae * 100.0) / 100.0,
                Math.round(dirAcc * 100.0) / 100.0,
                Math.round(gradeHit * 100.0) / 100.0,
                Math.round(avgTop * 1000.0) / 1000.0,
                Math.round(avgMarket * 1000.0) / 1000.0,
                Math.round(avgExcess * 1000.0) / 1000.0,
                summary,
                entries,
                Math.round(arimaMae * 100.0) / 100.0,
                Math.round(hwMae * 100.0) / 100.0,
                Math.round(linearMae * 100.0) / 100.0,
                optimalWeights
        );
    }

    // ------------------------------------------------------------------------
    // 行業輪動 Markov 模型
    // ------------------------------------------------------------------------

    /**
     * 行業輪動 Markov 模型 — 預測領漲行業轉換概率。
     *
     * 將行業按每日漲跌幅排名分為 3 個狀態：
     * 1=領漲（Top 1/3）、2=中間（Middle 1/3）、3=滯後（Bottom 1/3）
     *
     * @param lookbackDays 回溯天數（默認 30）
     * @return 輪動 Markov 分析 DTO
     */
    @Cacheable(value = CacheConfig.ROTATION_CACHE, key = "'rotation-markov-' + #p0")
    public RotationMarkovDto rotationMarkov(int lookbackDays) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusDays(lookbackDays + 10);

        List<IndustryDailyEntity> entities = industryDailyRepository
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(start, end);

        if (entities.isEmpty()) {
            return new RotationMarkovDto(end.toString(), 0, Map.of(), "數據不足，無法構建輪動 Markov 模型");
        }

        // 按日期分組
        Map<LocalDate, List<IndustryDailyEntity>> byDate = new LinkedHashMap<>();
        for (IndustryDailyEntity e : entities) {
            byDate.computeIfAbsent(e.getTradeDate(), k -> new ArrayList<>()).add(e);
        }

        List<LocalDate> sortedDates = new ArrayList<>(byDate.keySet());
        sortedDates.sort(LocalDate::compareTo);

        if (sortedDates.size() < 3) {
            return new RotationMarkovDto(end.toString(), 0, Map.of(), "交易日不足，無法構建輪動 Markov 模型");
        }

        // 每日按漲跌幅排名，分為 3 個狀態
        Map<LocalDate, Map<String, Integer>> dailyStates = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            List<IndustryDailyEntity> dayEntities = byDate.get(date);
            // 按漲跌幅排序
            List<IndustryDailyEntity> sorted = new ArrayList<>(dayEntities);
            sorted.sort((a, b) -> {
                double aPct = a.getAvgPctChg() != null ? a.getAvgPctChg().doubleValue() : 0;
                double bPct = b.getAvgPctChg() != null ? b.getAvgPctChg().doubleValue() : 0;
                return Double.compare(bPct, aPct); // 倒序
            });

            int n = sorted.size();
            int topThird = n / 3;
            int midThird = n * 2 / 3;

            Map<String, Integer> states = new LinkedHashMap<>();
            for (int i = 0; i < n; i++) {
                int state;
                if (i < topThird) state = 1; // 領漲
                else if (i < midThird) state = 2; // 中間
                else state = 3; // 滯後
                states.put(sorted.get(i).getIndustry(), state);
            }
            dailyStates.put(date, states);
        }

        // 按行業收集狀態序列
        Map<String, List<Integer>> industryStateSeries = new LinkedHashMap<>();
        for (LocalDate date : sortedDates) {
            Map<String, Integer> states = dailyStates.get(date);
            for (Map.Entry<String, Integer> e : states.entrySet()) {
                industryStateSeries.computeIfAbsent(e.getKey(), k -> new ArrayList<>()).add(e.getValue());
            }
        }

        Map<String, RotationMarkovDto.IndustryRotationMarkov> result = new LinkedHashMap<>();
        int totalTransitions = 0;

        for (Map.Entry<String, List<Integer>> entry : industryStateSeries.entrySet()) {
            String industry = entry.getKey();
            List<Integer> series = entry.getValue();
            if (series.size() < 3) continue;

            // 構建 3x3 轉移計數矩陣
            int[][] counts = new int[3][3];
            for (int i = 0; i < series.size() - 1; i++) {
                int from = series.get(i) - 1;
                int to = series.get(i + 1) - 1;
                if (from >= 0 && from < 3 && to >= 0 && to < 3) {
                    counts[from][to]++;
                    totalTransitions++;
                }
            }

            // 轉為概率矩陣
            double[][] matrix = new double[3][3];
            for (int i = 0; i < 3; i++) {
                int rowSum = 0;
                for (int j = 0; j < 3; j++) rowSum += counts[i][j];
                for (int j = 0; j < 3; j++) {
                    matrix[i][j] = rowSum > 0 ? (double) counts[i][j] / rowSum : 0.0;
                    matrix[i][j] = Math.round(matrix[i][j] * 10000.0) / 10000.0;
                }
                if (rowSum == 0) {
                    for (int j = 0; j < 3; j++) matrix[i][j] = 1.0 / 3;
                }
            }

            int currentState = series.get(series.size() - 1);
            String currentStateName = rotationStateName(currentState);

            // 下一期各狀態概率
            Map<Integer, Double> nextProb = new LinkedHashMap<>();
            int currentIdx = currentState - 1;
            for (int j = 0; j < 3; j++) {
                nextProb.put(j + 1, matrix[currentIdx][j]);
            }

            // 最可能下一狀態
            int mostLikelyNext = 1;
            double mostLikelyProb = 0;
            for (int j = 0; j < 3; j++) {
                if (matrix[currentIdx][j] > mostLikelyProb) {
                    mostLikelyProb = matrix[currentIdx][j];
                    mostLikelyNext = j + 1;
                }
            }

            // 穩態分布（3x3 迭代）
            Map<Integer, Double> steadyState = computeSteadyState3(matrix);
            double leaderProb = steadyState.getOrDefault(1, 0.0);

            int transitionCount = 0;
            for (int i = 0; i < 3; i++) {
                for (int j = 0; j < 3; j++) transitionCount += counts[i][j];
            }

            result.put(industry, new RotationMarkovDto.IndustryRotationMarkov(
                    industry,
                    matrix,
                    currentState,
                    currentStateName,
                    nextProb,
                    steadyState,
                    transitionCount,
                    rotationStateName(mostLikelyNext),
                    Math.round(mostLikelyProb * 1000.0) / 1000.0,
                    Math.round(leaderProb * 10000.0) / 10000.0
            ));
        }

        // 找長期領漲概率最高的行業
        List<Map.Entry<String, RotationMarkovDto.IndustryRotationMarkov>> sortedByLeader =
                new ArrayList<>(result.entrySet());
        sortedByLeader.sort((a, b) -> Double.compare(
                b.getValue().leaderProbability(), a.getValue().leaderProbability()));

        String summary = String.format(
                "分析區間 %s ~ %s，共 %d 次狀態轉換，%d 個行業。" +
                "長期領漲概率最高：%s（%.1f%%）。",
                start, end, totalTransitions, result.size(),
                sortedByLeader.isEmpty() ? "無" : sortedByLeader.get(0).getKey(),
                sortedByLeader.isEmpty() ? 0 : sortedByLeader.get(0).getValue().leaderProbability() * 100
        );

        return new RotationMarkovDto(end.toString(), totalTransitions, result, summary);
    }

    // ------------------------------------------------------------------------
    // 私有輔助方法
    // ------------------------------------------------------------------------

    /** 計算 Markov 鏈的穩態分布（迭代法）。 */
    private Map<Integer, Double> computeSteadyState(double[][] matrix) {
        // 初始均勻分布
        double[] state = {0.2, 0.2, 0.2, 0.2, 0.2};
        // 迭代 1000 次或收斂
        for (int iter = 0; iter < 1000; iter++) {
            double[] newState = new double[5];
            for (int j = 0; j < 5; j++) {
                for (int i = 0; i < 5; i++) {
                    newState[j] += state[i] * matrix[i][j];
                }
            }
            // 檢查收斂
            double maxDiff = 0;
            for (int i = 0; i < 5; i++) {
                maxDiff = Math.max(maxDiff, Math.abs(newState[i] - state[i]));
            }
            System.arraycopy(newState, 0, state, 0, 5);
            if (maxDiff < 1e-8) break;
        }

        Map<Integer, Double> result = new LinkedHashMap<>();
        for (int i = 0; i < 5; i++) {
            result.put(i + 1, Math.round(state[i] * 10000.0) / 10000.0);
        }
        return result;
    }

    /** 計算 3x3 Markov 鏈的穩態分布。 */
    private Map<Integer, Double> computeSteadyState3(double[][] matrix) {
        double[] state = {1.0 / 3, 1.0 / 3, 1.0 / 3};
        for (int iter = 0; iter < 1000; iter++) {
            double[] newState = new double[3];
            for (int j = 0; j < 3; j++) {
                for (int i = 0; i < 3; i++) {
                    newState[j] += state[i] * matrix[i][j];
                }
            }
            double maxDiff = 0;
            for (int i = 0; i < 3; i++) {
                maxDiff = Math.max(maxDiff, Math.abs(newState[i] - state[i]));
            }
            System.arraycopy(newState, 0, state, 0, 3);
            if (maxDiff < 1e-8) break;
        }

        Map<Integer, Double> result = new LinkedHashMap<>();
        for (int i = 0; i < 3; i++) {
            result.put(i + 1, Math.round(state[i] * 10000.0) / 10000.0);
        }
        return result;
    }

    /** 等級數值轉名稱。 */
    private static String gradeName(int level) {
        return switch (level) {
            case 5 -> "繁榮";
            case 4 -> "景氣";
            case 3 -> "平穩";
            case 2 -> "低迷";
            case 1 -> "衰退";
            default -> "未知";
        };
    }

    /** 輪動狀態名稱。 */
    private static String rotationStateName(int state) {
        return switch (state) {
            case 1 -> "領漲";
            case 2 -> "中間";
            case 3 -> "滯後";
            default -> "未知";
        };
    }

    /** ARIMA 簡化版預測：AR(2) + 一階差分。 */
    private double[] forecastARIMA(double[] data, int steps) {
        int n = data.length;
        if (n < 4) {
            double last = n > 0 ? data[n - 1] : 50.0;
            double[] result = new double[steps];
            for (int i = 0; i < steps; i++) result[i] = last;
            return result;
        }

        // 一階差分
        double[] diff = new double[n - 1];
        for (int i = 0; i < n - 1; i++) {
            diff[i] = data[i + 1] - data[i];
        }

        // AR(2) on differenced data: diff[t] = a*diff[t-1] + b*diff[t-2] + c
        // 用最小二乘法估計 a, b, c
        double[] ar2 = fitAR2(diff);

        // 預測差分
        double[] forecastDiff = new double[steps];
        double prevDiff1 = diff[diff.length - 1];
        double prevDiff2 = diff.length > 1 ? diff[diff.length - 2] : 0;
        for (int i = 0; i < steps; i++) {
            forecastDiff[i] = ar2[0] * prevDiff1 + ar2[1] * prevDiff2 + ar2[2];
            prevDiff2 = prevDiff1;
            prevDiff1 = forecastDiff[i];
        }

        // 反差分還原
        double[] forecast = new double[steps];
        double lastVal = data[n - 1];
        for (int i = 0; i < steps; i++) {
            lastVal += forecastDiff[i];
            forecast[i] = Math.max(0, Math.min(100, lastVal));
        }
        return forecast;
    }

    /** AR(2) 係數估計（最小二乘法）。需 ≥5 個點使 m=n-2≥3 方程式覆蓋 3 未知數。 */
    private double[] fitAR2(double[] data) {
        int n = data.length;
        if (n < 5) return new double[]{0, 0, 0};

        // 構建回歸矩陣: y = X * beta
        // y[i] = data[i+2], X[i] = [data[i+1], data[i], 1]
        int m = n - 2;
        double[][] X = new double[m][3];
        double[] y = new double[m];
        for (int i = 0; i < m; i++) {
            X[i][0] = data[i + 1];
            X[i][1] = data[i];
            X[i][2] = 1;
            y[i] = data[i + 2];
        }

        // 正規方程: beta = (X^T X)^-1 X^T y
        // X^T X (3x3)
        double[][] XtX = new double[3][3];
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 3; j++) {
                for (int k = 0; k < m; k++) {
                    XtX[i][j] += X[k][i] * X[k][j];
                }
            }
        }
        // X^T y (3x1)
        double[] Xty = new double[3];
        for (int i = 0; i < 3; i++) {
            for (int k = 0; k < m; k++) {
                Xty[i] += X[k][i] * y[k];
            }
        }
        // 解 3x3 線性方程組（高斯消去法）
        return solveLinearSystem(XtX, Xty);
    }

    /** Holt-Winters 三重指數平滑預測。 */
    private double[] forecastHoltWinters(double[] data, int steps, int seasonLength) {
        int n = data.length;
        if (n < seasonLength * 2) {
            // 數據不足，用簡單移動平均
            double avg = 0;
            int lookback = Math.min(5, n);
            for (int i = n - lookback; i < n; i++) avg += data[i];
            avg /= lookback;
            double[] result = new double[steps];
            for (int i = 0; i < steps; i++) result[i] = avg;
            return result;
        }

        double alpha = 0.3; // 水平平滑係數
        double beta = 0.1;  // 趨勢平滑係數
        double gamma = 0.2; // 季節平滑係數

        // 初始化
        double level = 0;
        for (int i = 0; i < seasonLength; i++) level += data[i];
        level /= seasonLength;

        double trend = 0;
        for (int i = 0; i < seasonLength; i++) {
            trend += (data[seasonLength + i] - data[i]);
        }
        trend /= seasonLength;

        double[] seasonals = new double[seasonLength];
        for (int i = 0; i < seasonLength; i++) {
            seasonals[i] = data[i] - level;
        }

        // 迭代更新
        for (int i = seasonLength; i < n; i++) {
            double val = data[i];
            double lastLevel = level;
            int seasonIdx = i % seasonLength;

            level = alpha * (val - seasonals[seasonIdx]) + (1 - alpha) * (level + trend);
            trend = beta * (level - lastLevel) + (1 - beta) * trend;
            seasonals[seasonIdx] = gamma * (val - level) + (1 - gamma) * seasonals[seasonIdx];
        }

        // 預測
        double[] forecast = new double[steps];
        for (int i = 0; i < steps; i++) {
            int seasonIdx = (n + i) % seasonLength;
            forecast[i] = Math.max(0, Math.min(100, level + (i + 1) * trend + seasonals[seasonIdx]));
        }
        return forecast;
    }

    /** 線性回歸預測（OLS）。 */
    private double[] forecastLinearRegression(double[] data, int steps) {
        int n = data.length;
        if (n < 3) {
            double last = n > 0 ? data[n - 1] : 50.0;
            double[] result = new double[steps];
            for (int i = 0; i < steps; i++) result[i] = last;
            return result;
        }

        // OLS: y = a + b * x
        double sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        for (int i = 0; i < n; i++) {
            sumX += i;
            sumY += data[i];
            sumXY += i * data[i];
            sumX2 += (double) i * i;
        }
        double meanX = sumX / n;
        double meanY = sumY / n;

        double denominator = n * sumX2 - sumX * sumX;
        if (denominator == 0) {
            // 所有 x 值相同（如輸入為常數序列），無法擬合斜率，退化為水平預測
            double[] forecast = new double[steps];
            for (int i = 0; i < steps; i++) forecast[i] = Math.max(0, Math.min(100, meanY));
            return forecast;
        }
        double b = (n * sumXY - sumX * sumY) / denominator;
        double a = meanY - b * meanX;

        // 預測
        double[] forecast = new double[steps];
        for (int i = 0; i < steps; i++) {
            forecast[i] = Math.max(0, Math.min(100, a + b * (n + i)));
        }
        return forecast;
    }

    /** 判斷趨勢。 */
    private static String judgeTrend(double current, double forecast) {
        double delta = forecast - current;
        if (delta > 3) return "上升";
        if (delta < -3) return "下降";
        return "平穩";
    }

    /** 三模型共識趨勢（多數決）。 */
    private static String consensusTrend(String a, String b, String c) {
        int up = 0, down = 0, flat = 0;
        if ("上升".equals(a)) up++;
        else if ("下降".equals(a)) down++;
        else flat++;
        if ("上升".equals(b)) up++;
        else if ("下降".equals(b)) down++;
        else flat++;
        if ("上升".equals(c)) up++;
        else if ("下降".equals(c)) down++;
        else flat++;

        if (up >= 2) return "上升";
        if (down >= 2) return "下降";
        return "平穩";
    }

    /** P4-3: 根據各模型 MAE 計算逆 MAE 最優權重（MAE 越小權重越大）。 */
    private static String computeOptimalWeights(double arimaMae, double hwMae, double linearMae) {
        double[] w = inverseMaeWeights(arimaMae, hwMae, linearMae);
        if (w == null) return "N/A（數據不足）";
        return String.format("ARIMA %.2f / HW %.2f / LR %.2f", w[0], w[1], w[2]);
    }

    /** 當前預測使用的權重來源標籤（"fixed" 或 "adaptive"），用於 DTO 與緩存鍵。 */
    private String weightSourceLabel() {
        return appProperties.getForecast().isAdaptiveWeights() ? "adaptive" : "fixed";
    }

    /**
     * 滾動窗口逆 MAE 自適應集成權重計算（避免 look-ahead bias）。
     * <p>
     * 在過去 {@code windowDays} 個時間點構成的滾動窗口內，對每個時間點 t 做 one-step-ahead 預測：
     * 預測 data[t] 時<strong>只用 data[0..t-1]</strong>（截至 t 的歷史），絕不接觸 t 及之後的數據，
     * 從而杜絕 look-ahead bias。累計各模型絕對誤差得到 MAE，再以逆 MAE 歸一化得到動態權重。
     *
     * <h3>look-ahead bias 防護設計</h3>
     * <ul>
     *   <li>每個時間點的預測輸入 {@code Arrays.copyOf(data, t)} 只含索引 0..t-1，不包含目標值 data[t]。</li>
     *   <li>評估窗口僅取歷史區間 [evalStart, n)，不觸及未來預測目標。</li>
     *   <li>數據不足（無法構成有效窗口）時回退到固定權重，保證永不拋異常。</li>
     * </ul>
     *
     * @param data       景氣度歷史序列（按時間升序）
     * @param windowDays 滾動窗口天數（評估的歷史時間點數量）
     * @return {@code double[3]}：[ARIMA 權重, HW 權重, LR 權重]，和為 1.0
     */
    double[] computeAdaptiveWeights(double[] data, int windowDays) {
        int n = data.length;
        // 評估窗口起點：確保每個預測點之前至少有 10 個歷史點供模型擬合
        int minHistory = 10;
        int evalStart = Math.max(minHistory, n - Math.max(1, windowDays));
        if (evalStart >= n - 1) {
            // 數據不足以構成滾動窗口，回退到固定權重
            return new double[]{W_ARIMA, W_HW, W_LR};
        }

        double totalArimaError = 0;
        double totalHwError = 0;
        double totalLinearError = 0;
        int count = 0;

        for (int t = evalStart; t < n; t++) {
            // 關鍵：只用 data[0..t-1] 預測 data[t]，不接觸 t 及之後的數據（無 look-ahead bias）
            double[] history = Arrays.copyOf(data, t);
            double[] arimaF = forecastARIMA(history, 1);
            double[] hwF = forecastHoltWinters(history, 1, HW_SEASON_LENGTH);
            double[] linearF = forecastLinearRegression(history, 1);
            double actual = data[t];
            totalArimaError += Math.abs(arimaF[0] - actual);
            totalHwError += Math.abs(hwF[0] - actual);
            totalLinearError += Math.abs(linearF[0] - actual);
            count++;
        }

        if (count == 0) {
            return new double[]{W_ARIMA, W_HW, W_LR};
        }
        double arimaMae = totalArimaError / count;
        double hwMae = totalHwError / count;
        double linearMae = totalLinearError / count;
        double[] w = inverseMaeWeights(arimaMae, hwMae, linearMae);
        return w != null ? w : new double[]{W_ARIMA, W_HW, W_LR};
    }

    /**
     * 逆 MAE 權重歸一化：{@code w_i = (1/mae_i) / sum(1/mae_j)}。
     * <p>
     * MAE 越小（模型越準）權重越大。當所有 MAE 都接近 0 或數據不足時返回 {@code null}（由調用方回退）。
     *
     * @return {@code double[3]} 歸一化權重（和為 1.0），或 {@code null} 表示無法計算
     */
    private static double[] inverseMaeWeights(double arimaMae, double hwMae, double linearMae) {
        double invArima = arimaMae > 0.01 ? 1.0 / arimaMae : 0;
        double invHw = hwMae > 0.01 ? 1.0 / hwMae : 0;
        double invLinear = linearMae > 0.01 ? 1.0 / linearMae : 0;
        double sum = invArima + invHw + invLinear;
        if (sum < 1e-9) return null;
        return new double[]{invArima / sum, invHw / sum, invLinear / sum};
    }

    /** 高斯消去法解線性方程組 Ax=b。 */
    private static double[] solveLinearSystem(double[][] A, double[] b) {
        int n = b.length;
        // 增廣矩陣
        double[][] aug = new double[n][n + 1];
        for (int i = 0; i < n; i++) {
            System.arraycopy(A[i], 0, aug[i], 0, n);
            aug[i][n] = b[i];
        }
        // 前向消去
        for (int col = 0; col < n; col++) {
            // 部分選主元
            int maxRow = col;
            for (int row = col + 1; row < n; row++) {
                if (Math.abs(aug[row][col]) > Math.abs(aug[maxRow][col])) {
                    maxRow = row;
                }
            }
            double[] tmp = aug[col];
            aug[col] = aug[maxRow];
            aug[maxRow] = tmp;

            if (Math.abs(aug[col][col]) < 1e-12) continue; // 奇異

            for (int row = col + 1; row < n; row++) {
                double factor = aug[row][col] / aug[col][col];
                for (int j = col; j <= n; j++) {
                    aug[row][j] -= factor * aug[col][j];
                }
            }
        }
        // 回代
        double[] x = new double[n];
        for (int i = n - 1; i >= 0; i--) {
            x[i] = aug[i][n];
            for (int j = i + 1; j < n; j++) {
                x[i] -= aug[i][j] * x[j];
            }
            if (Math.abs(aug[i][i]) > 1e-12) {
                x[i] /= aug[i][i];
            }
        }
        return x;
    }

    /** double[] 轉 List<Double>（四捨五入到小數點 2 位）。 */
    private static List<Double> toList(double[] arr) {
        List<Double> list = new ArrayList<>(arr.length);
        for (double v : arr) {
            list.add(Math.round(v * 100.0) / 100.0);
        }
        return list;
    }

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
}
