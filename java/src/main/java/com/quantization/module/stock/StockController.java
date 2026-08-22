package com.quantization.module.stock;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.forecast.ForecastService;
import com.quantization.module.industry.IndustryService;
import com.quantization.module.stock.dto.HotSymbolDto;
import com.quantization.module.stock.dto.IndustryDailyDto;
import com.quantization.module.stock.dto.IndustryProsperityDto;
import com.quantization.module.stock.dto.RotationPredictionDto;
import com.quantization.module.stock.dto.RotationBacktestDto;
import com.quantization.module.stock.dto.RotationAutoMlDto;
import com.quantization.module.stock.dto.ProsperityAlertDto;
import com.quantization.module.stock.dto.ProsperitySeasonalityDto;
import com.quantization.module.stock.dto.ProsperityMarkovDto;
import com.quantization.module.stock.dto.ProsperityForecastDto;
import com.quantization.module.stock.dto.ProsperityForecastBacktestDto;
import com.quantization.module.stock.dto.RotationMarkovDto;
import com.quantization.module.stock.dto.IndexDailyDto;
import com.quantization.module.stock.dto.IndexHistoryBatchRequestDto;
import com.quantization.module.stock.dto.IndexMetadataDto;
import com.quantization.module.stock.dto.MarketBreadthDto;
import com.quantization.module.stock.dto.RotationSignalDto;
import com.quantization.module.stock.dto.SectorPerformanceDto;
import com.quantization.module.stock.dto.SearchResultDto;
import com.quantization.module.stock.dto.StockDailyDto;
import com.quantization.module.stock.dto.StockDailyQueryDto;
import com.quantization.module.stock.dto.StockIndustryDto;
import com.quantization.module.stock.dto.StockSuggestionDto;
import com.quantization.module.stock.dto.SummaryMetricsDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * 行情 Controller，提供汇总指标、日线查询、波动榜、搜索建议、行业分类、指数分析等接口。
 */
@Tag(name = "行情 stock")
@RestController
@RequestMapping("/api/stock")
public class StockController {

    private final StockService stockService;
    private final IndustryService industryService;
    private final ForecastService forecastService;
    private final StockIndustryRepository industryRepository;
    private final IndexDailyRepository indexDailyRepository;
    private final IndexMetadataRepository indexMetadataRepository;
    private final com.quantization.module.system.NotificationService notificationService;

    public StockController(
            StockService stockService,
            IndustryService industryService,
            ForecastService forecastService,
            StockIndustryRepository industryRepository,
            IndexDailyRepository indexDailyRepository,
            IndexMetadataRepository indexMetadataRepository,
            com.quantization.module.system.NotificationService notificationService) {
        this.stockService = stockService;
        this.industryService = industryService;
        this.forecastService = forecastService;
        this.industryRepository = industryRepository;
        this.indexDailyRepository = indexDailyRepository;
        this.indexMetadataRepository = indexMetadataRepository;
        this.notificationService = notificationService;
    }

    /**
     * 获取汇总指标（总记录数、股票数、最新交易日等）。
     * <p>
     * 已弃用：前端统一使用 {@code /api/dashboard/summary}（走 Caffeine 缓存）。
     * 此端点与 DashboardController#summary 功能重复，保留仅为向后兼容。
     *
     * @return 汇总指标 DTO
     */
    @Deprecated(forRemoval = true)
    @Operation(summary = "汇总指标（已弃用，请用 /api/dashboard/summary）")
    @GetMapping("/summary")
    public ApiResponse<SummaryMetricsDto> summary() {
        return ApiResponse.ok(stockService.summaryMetrics());
    }

    /**
     * 日线表格查询（分页），支持按代码、复权方式和日期区间筛选。
     *
     * @param code       股票代码（可选）
     * @param adjustflag 复权方式（默认 3）
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @param limit      每页条数（默认 50）
     * @param offset     偏移量（默认 0）
     * @return 分页搜索结果
     */
    @Operation(summary = "日线表格查询（分页）")
    @GetMapping("/search")
    public ApiResponse<SearchResultDto> search(
            @RequestParam(required = false) String code,
            @RequestParam(required = false, defaultValue = "3") Integer adjustflag,
            @RequestParam(required = false) LocalDate startDate,
            @RequestParam(required = false) LocalDate endDate,
            @RequestParam(required = false, defaultValue = "50") Integer limit,
            @RequestParam(required = false, defaultValue = "0") Integer offset) {
        StockDailyQueryDto dto = new StockDailyQueryDto(code, adjustflag, startDate, endDate, limit, offset);
        return ApiResponse.ok(stockService.searchDailyPaged(dto));
    }

    /**
     * 获取最新交易日波动最大的股票（按 |涨跌幅| 排序）。
     *
     * @param limit 返回条数（默认 8）
     * @return 波动榜列表
     */
    @Operation(summary = "最新波动")
    @GetMapping("/movers")
    public ApiResponse<List<HotSymbolDto>> movers(@RequestParam(required = false, defaultValue = "8") int limit) {
        return ApiResponse.ok(stockService.latestMovers(limit));
    }

    /**
     * 搜索建議（自動補全），根據用戶輸入的部分代碼返回最新交易日的匹配股票。
     *
     * @param q     搜索关键词
     * @param limit 返回条数（默认 10）
     * @return 搜索建议列表
     */
    @Operation(summary = "搜索建議（自動補全）")
    @GetMapping("/suggest")
    public ApiResponse<List<StockSuggestionDto>> suggest(
            @RequestParam String q,
            @RequestParam(required = false, defaultValue = "10") int limit) {
        return ApiResponse.ok(stockService.suggest(q, limit));
    }

    // ===== 行業分類 =====

    /**
     * 查詢行業分類，支持按代碼或行業關鍵詞篩選，無參數時返回全部。
     *
     * @param code     股票代码（可選）
     * @param industry 行業關鍵詞（可選）
     * @return 行業分類列表
     */
    @Operation(summary = "查詢所有行業分類")
    @GetMapping("/industries")
    public ApiResponse<List<StockIndustryDto>> industries(
            @RequestParam(required = false) String code,
            @RequestParam(required = false) String industry) {
        if (code != null && !code.isBlank()) {
            return ApiResponse.ok(industryRepository.findByCode(code).stream()
                    .map(StockIndustryDto::from).toList());
        }
        if (industry != null && !industry.isBlank()) {
            return ApiResponse.ok(industryRepository.findByIndustryContaining(industry).stream()
                    .map(StockIndustryDto::from).toList());
        }
        return ApiResponse.ok(industryRepository.findAllByOrderByCodeAsc().stream()
                .map(StockIndustryDto::from).toList());
    }

    /**
     * 查詢所有不同行業名稱列表。
     *
     * @return 行業名稱列表
     */
    @Operation(summary = "查詢所有不同行業列表")
    @GetMapping("/industries/list")
    public ApiResponse<List<String>> industryList() {
        return ApiResponse.ok(industryRepository.findDistinctIndustries());
    }

    // ===== 行業日聚合 =====

    /**
     * 查詢指定交易日的行業聚合數據。
     * 用於行業熱力圖、漲跌家數統計等。
     *
     * @param tradeDate 交易日期（可選，默認最新交易日）
     * @return 行業聚合列表（按平均漲跌幅倒序）
     */
    @Operation(summary = "行業日聚合數據")
    @GetMapping("/industry-daily")
    public ApiResponse<List<IndustryDailyDto>> industryDaily(
            @RequestParam(required = false) LocalDate tradeDate) {
        return ApiResponse.ok(industryService.industryDailyByDate(tradeDate));
    }

    /**
     * 查詢指定行業在日期區間內的聚合數據。
     *
     * @param industry 行業名稱
     * @param start    起始日期
     * @param end      結束日期
     * @return 行業聚合列表（按日期升序）
     */
    @Operation(summary = "行業日聚合區間數據")
    @GetMapping("/industry-daily/range")
    public ApiResponse<List<IndustryDailyDto>> industryDailyRange(
            @RequestParam String industry,
            @RequestParam LocalDate start,
            @RequestParam LocalDate end) {
        return ApiResponse.ok(industryService.industryDailyRange(industry, start, end));
    }

    /**
     * 查詢日期區間內全部行業的聚合數據（用於行業相關性矩陣）。
     *
     * @param start 起始日期
     * @param end   結束日期
     * @return 全部行業聚合列表（按日期升序、行業升序）
     */
    @Operation(summary = "全部行業日聚合區間數據（相關性矩陣用）")
    @GetMapping("/industry-daily/all-range")
    public ApiResponse<List<IndustryDailyDto>> allIndustryDailyRange(
            @RequestParam LocalDate start,
            @RequestParam LocalDate end) {
        return ApiResponse.ok(industryService.allIndustryDailyRange(start, end));
    }

    /**
     * 行業景氣度指標 — 基於漲跌幅、成交額、換手率、漲跌家數綜合評分。
     *
     * @param tradeDate 交易日期，為空時取最新交易日
     * @return 行業景氣度 DTO 列表（按景氣度倒序）
     */
    @Operation(summary = "行業景氣度指標（綜合評分）")
    @GetMapping("/industry-prosperity")
    public ApiResponse<List<IndustryProsperityDto>> industryProsperity(
            @RequestParam(required = false) LocalDate tradeDate) {
        return ApiResponse.ok(industryService.industryProsperity(tradeDate));
    }

    /**
     * 行業景氣度歷史趨勢 — 指定日期區間內每個交易日的行業景氣度。
     *
     * @param start 起始日期
     * @param end   結束日期
     * @param topN  每個日期返回的行業數（默認 15）
     * @return 行業景氣度 DTO 列表（按日期升序、景氣度倒序）
     */
    @Operation(summary = "行業景氣度歷史趨勢（多日對比）")
    @GetMapping("/industry-prosperity/range")
    public ApiResponse<List<IndustryProsperityDto>> industryProsperityRange(
            @RequestParam LocalDate start,
            @RequestParam LocalDate end,
            @RequestParam(required = false, defaultValue = "15") int topN) {
        return ApiResponse.ok(industryService.industryProsperityRange(start, end, topN));
    }

    /**
     * 行業輪動預測 — 基於歷史輪動規律預測下一輪領漲行業。
     *
     * @param lookbackDays 回溯天數（默認 20）
     * @return 輪動預測 DTO
     */
    @Operation(summary = "行業輪動預測（歷史規律預測下一輪領漲）")
    @GetMapping("/rotation-prediction")
    public ApiResponse<RotationPredictionDto> rotationPrediction(
            @RequestParam(required = false, defaultValue = "20") int lookbackDays) {
        return ApiResponse.ok(forecastService.predictRotation(lookbackDays));
    }

    /**
     * 行業輪動預測回測 — 驗證歷史預測準確率。
     *
     * @param lookbackDays  預測回溯天數（默認 20）
     * @param forwardDays   前瞻驗證天數（默認 5）
     * @param backtestDays  回測總天數（默認 90）
     * @return 回測結果 DTO
     */
    @Operation(summary = "輪動預測回測（歷史預測準確率驗證）")
    @GetMapping("/rotation-prediction/backtest")
    public ApiResponse<RotationBacktestDto> rotationPredictionBacktest(
            @RequestParam(required = false, defaultValue = "20") int lookbackDays,
            @RequestParam(required = false, defaultValue = "5") int forwardDays,
            @RequestParam(required = false, defaultValue = "90") int backtestDays) {
        return ApiResponse.ok(forecastService.backtestRotationPrediction(lookbackDays, forwardDays, backtestDays));
    }

    /**
     * 輪動預測 AutoML 自動調參 — 自動尋找最佳 lookback/forward 組合。
     *
     * <p>採用嚴格日期隔離 out-of-sample 評估：調參只用區間 A，評估只用區間 B（B 在 A 之後，不重疊）。
     * 不傳日期參數時，默認前 70% 區間調參、後 30% 區間評估。
     *
     * @param backtestDays  回測總天數（默認 90，用於計算默認分割區間）
     * @param tuneStartDate 調參區間 A 起始日期（可選，格式 yyyy-MM-dd）
     * @param tuneEndDate   調參區間 A 結束日期（可選）
     * @param evalStartDate 評估區間 B 起始日期（可選，須在 tuneEndDate 之後）
     * @param evalEndDate   評估區間 B 結束日期（可選）
     * @return AutoML 結果 DTO
     */
    @Operation(summary = "輪動預測 AutoML 自動調參（嚴格日期隔離 out-of-sample 評估）")
    @GetMapping("/rotation-prediction/automl")
    public ApiResponse<RotationAutoMlDto> rotationPredictionAutoMl(
            @RequestParam(required = false, defaultValue = "90") int backtestDays,
            @RequestParam(required = false) LocalDate tuneStartDate,
            @RequestParam(required = false) LocalDate tuneEndDate,
            @RequestParam(required = false) LocalDate evalStartDate,
            @RequestParam(required = false) LocalDate evalEndDate) {
        return ApiResponse.ok(forecastService.autoTuneRotationPrediction(
                backtestDays, tuneStartDate, tuneEndDate, evalStartDate, evalEndDate));
    }

    /**
     * 行業景氣度異常預警 — 檢測景氣度突變與等級躍遷。
     *
     * @param threshold 突變閾值（默認 10.0）
     * @return 景氣度預警 DTO
     */
    @Operation(summary = "行業景氣度異常預警（突變與等級躍遷）")
    @GetMapping("/industry-prosperity/alerts")
    public ApiResponse<ProsperityAlertDto> prosperityAlerts(
            @RequestParam(required = false, defaultValue = "10.0") double threshold,
            @RequestParam(required = false, defaultValue = "false") boolean notify) {
        ProsperityAlertDto result = industryService.prosperityAlerts(threshold);
        // 若請求通知且有預警，異步發送郵件/Webhook
        if (notify && !result.alerts().isEmpty()) {
            java.util.List<java.util.Map<String, Object>> alertMaps = new java.util.ArrayList<>();
            for (ProsperityAlertDto.AlertEntry a : result.alerts()) {
                java.util.Map<String, Object> m = new java.util.LinkedHashMap<>();
                m.put("industry", a.industry());
                m.put("alertType", a.alertType());
                m.put("alertTypeName", a.alertTypeName());
                m.put("severity", a.severity());
                m.put("message", a.message());
                m.put("yesterdayProsperity", a.yesterdayProsperity());
                m.put("todayProsperity", a.todayProsperity());
                m.put("change", a.change());
                m.put("yesterdayGrade", a.yesterdayGrade());
                m.put("todayGrade", a.todayGrade());
                alertMaps.add(m);
            }
            notificationService.sendProsperityAlertNotification(result.analysisDate(), result.summary(), alertMaps);
        }
        return ApiResponse.ok(result);
    }

    /**
     * 行業景氣度週期性分析 — 檢測季節性模式與週期規律。
     *
     * @param months 分析回溯月數（默認 12）
     * @return 週期性分析 DTO
     */
    @Operation(summary = "行業景氣度週期性分析（季節性模式）")
    @GetMapping("/industry-prosperity/seasonality")
    public ApiResponse<ProsperitySeasonalityDto> prosperitySeasonality(
            @RequestParam(required = false, defaultValue = "12") int months) {
        months = Math.max(1, Math.min(60, months));
        return ApiResponse.ok(forecastService.prosperitySeasonality(months));
    }

    /**
     * 行業景氣度 Markov 狀態轉移模型 — 預測等級轉換概率。
     *
     * @param months 分析回溯月數（默認 12）
     * @return Markov 分析 DTO
     */
    @Operation(summary = "行業景氣度 Markov 狀態轉移模型")
    @GetMapping("/industry-prosperity/markov")
    public ApiResponse<ProsperityMarkovDto> prosperityMarkov(
            @RequestParam(required = false, defaultValue = "12") int months) {
        months = Math.max(1, Math.min(36, months));
        return ApiResponse.ok(forecastService.prosperityMarkov(months));
    }

    /**
     * 行業景氣度多模型預測 — ARIMA + Holt-Winters + 線性回歸。
     *
     * @param months       分析回溯月數（默認 6）
     * @param forecastDays 預測天數（默認 5）
     * @return 多模型預測 DTO
     */
    @Operation(summary = "行業景氣度多模型預測（ARIMA + Holt-Winters + 線性回歸）")
    @GetMapping("/industry-prosperity/forecast")
    public ApiResponse<ProsperityForecastDto> prosperityForecast(
            @RequestParam(required = false, defaultValue = "6") int months,
            @RequestParam(required = false, defaultValue = "5") int forecastDays) {
        months = Math.max(1, Math.min(24, months));
        forecastDays = Math.max(1, Math.min(20, forecastDays));
        return ApiResponse.ok(forecastService.prosperityForecast(months, forecastDays));
    }

    /**
     * 行業景氣度預測回測 — 驗證多模型預測的歷史準確率。
     *
     * @param months       分析回溯月數（默認 6）
     * @param forecastDays 預測天數（默認 5）
     * @param backtestDays 回測總天數（默認 60）
     * @return 回測結果 DTO
     */
    @Operation(summary = "景氣度預測回測（歷史預測準確率驗證）")
    @GetMapping("/industry-prosperity/forecast/backtest")
    public ApiResponse<ProsperityForecastBacktestDto> prosperityForecastBacktest(
            @RequestParam(required = false, defaultValue = "6") int months,
            @RequestParam(required = false, defaultValue = "5") int forecastDays,
            @RequestParam(required = false, defaultValue = "60") int backtestDays) {
        // 安全邊界：限制參數範圍，防止數據庫過載
        months = Math.max(1, Math.min(24, months));
        forecastDays = Math.max(1, Math.min(20, forecastDays));
        backtestDays = Math.max(10, Math.min(180, backtestDays));
        return ApiResponse.ok(forecastService.prosperityForecastBacktest(months, forecastDays, backtestDays));
    }

    /**
     * 行業輪動 Markov 模型 — 預測領漲行業轉換概率。
     *
     * @param lookbackDays 回溯天數（默認 30）
     * @return 輪動 Markov 分析 DTO
     */
    @Operation(summary = "行業輪動 Markov 模型（領漲行業轉換概率）")
    @GetMapping("/rotation-markov")
    public ApiResponse<RotationMarkovDto> rotationMarkov(
            @RequestParam(required = false, defaultValue = "30") int lookbackDays) {
        // 安全邊界：限制回溯天數，防止數據庫過載
        lookbackDays = Math.max(5, Math.min(180, lookbackDays));
        return ApiResponse.ok(forecastService.rotationMarkov(lookbackDays));
    }

    // ===== 指數歷史（市場形態識別）=====

    /**
     * 查詢指數最近 N 日的歷史數據（用於市場形態識別）。
     *
     * @param code   指數代碼（如 sh.000001）
     * @param days   最近天數（默認 10）
     * @return 指數日線列表（按日期升序）
     */
    @Operation(summary = "指數最近N日歷史（市場形態識別）")
    @GetMapping("/index-history")
    public ApiResponse<List<IndexDailyDto>> indexHistory(
            @RequestParam String code,
            @RequestParam(required = false, defaultValue = "10") int days) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusDays(days + 5); // 多取幾天以防非交易日
        List<IndexDailyEntity> entities = indexDailyRepository
                .findByCodeAndTradeDateBetweenOrderByTradeDateAsc(code, start, end);
        // 只取最近 days 條
        int size = entities.size();
        if (size > days) {
            entities = entities.subList(size - days, size);
        }
        return ApiResponse.ok(entities.stream().map(IndexDailyDto::from).toList());
    }

    /**
     * 批量查詢多個指數最近 N 日的歷史數據。
     * 用於 AI 多維市場分析（大盤 + 風格 + 行業）。
     *
     * @param request 指數代碼列表 + 天數
     * @return 按指數代碼分組的歷史數據
     */
    @Operation(summary = "批量指數最近N日歷史")
    @PostMapping("/index-history/batch")
    public ApiResponse<Map<String, List<IndexDailyDto>>> indexHistoryBatch(
            @RequestBody IndexHistoryBatchRequestDto request) {
        return ApiResponse.ok(stockService.batchIndexHistory(request.codes(), request.days()));
    }

    // ===== 多日板塊表現（10日行情分析）=====

    /**
     * 查詢最近 N 個交易日的板塊表現（各行業平均漲跌幅 + 領漲股）。
     * 用於 AI 10日行情分析，識別利好/利空行業及其延續性。
     *
     * @param days 最近交易日天數（默認 10）
     * @return 板塊表現列表（按日期倒序、行業平均漲跌幅倒序）
     */
    @Operation(summary = "多日板塊表現（10日行情分析）")
    @GetMapping("/sector-performance")
    public ApiResponse<List<SectorPerformanceDto>> sectorPerformance(
            @RequestParam(required = false, defaultValue = "10") int days) {
        return ApiResponse.ok(stockService.sectorPerformance(days));
    }

    // ===== 多維市場分析（廣度 + 輪動）=====

    /**
     * 市場廣度分析：基於綜合/規模/成長/價值/主題/行業指數，判斷市場整體強弱與一致性。
     *
     * @param days 最近交易日天數（默認 10）
     * @return 市場廣度 DTO
     */
    @Operation(summary = "市場廣度分析（多維指數）")
    @GetMapping("/market-breadth")
    public ApiResponse<MarketBreadthDto> marketBreadth(
            @RequestParam(required = false, defaultValue = "10") int days) {
        return ApiResponse.ok(stockService.marketBreadth(days));
    }

    /**
     * 輪動信號分析：基於一級/二級行業指數和成長/價值指數，計算風格與行業輪動方向。
     *
     * @param days 最近交易日天數（默認 10）
     * @return 輪動信號 DTO
     */
    @Operation(summary = "輪動信號分析（行業與風格輪動）")
    @GetMapping("/rotation")
    public ApiResponse<RotationSignalDto> rotationSignals(
            @RequestParam(required = false, defaultValue = "10") int days) {
        return ApiResponse.ok(stockService.rotationSignals(days));
    }

    // ===== 指數元數據（10 大類別 ~80 個指數）=====

    /**
     * 查詢全部指數元數據列表（代碼/名稱/分類）。
     * 數據來源：ingestion/index_list.json → index_metadata 表。
     *
     * @param categoryCode 可選，按分類英文代碼過濾（composite/scale/industry_l1/industry_l2/strategy/growth/value/theme/fund/bond）
     * @return 指數元數據列表
     */
    @Operation(summary = "指數元數據列表（10 大類別）")
    @GetMapping("/index-list")
    public ApiResponse<List<IndexMetadataDto>> indexList(
            @RequestParam(required = false) String categoryCode) {
        List<IndexMetadataEntity> entities;
        if (categoryCode != null && !categoryCode.isBlank()) {
            entities = indexMetadataRepository.findByCategoryCodeOrderByCodeAsc(categoryCode);
        } else {
            entities = indexMetadataRepository.findAllByOrderByCategoryCodeAscCodeAsc();
        }
        return ApiResponse.ok(entities.stream().map(IndexMetadataDto::from).toList());
    }
}
