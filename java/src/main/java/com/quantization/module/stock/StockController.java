package com.quantization.module.stock;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.stock.dto.HotSymbolDto;
import com.quantization.module.stock.dto.IndustryDailyDto;
import com.quantization.module.stock.dto.IndustryProsperityDto;
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
    private final StockIndustryRepository industryRepository;
    private final IndexDailyRepository indexDailyRepository;
    private final IndexMetadataRepository indexMetadataRepository;

    public StockController(
            StockService stockService,
            StockIndustryRepository industryRepository,
            IndexDailyRepository indexDailyRepository,
            IndexMetadataRepository indexMetadataRepository) {
        this.stockService = stockService;
        this.industryRepository = industryRepository;
        this.indexDailyRepository = indexDailyRepository;
        this.indexMetadataRepository = indexMetadataRepository;
    }

    /**
     * 获取汇总指标（总记录数、股票数、最新交易日等）。
     *
     * @return 汇总指标 DTO
     */
    @Operation(summary = "汇总指标")
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
        return ApiResponse.ok(stockService.industryDailyByDate(tradeDate));
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
        return ApiResponse.ok(stockService.industryDailyRange(industry, start, end));
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
        return ApiResponse.ok(stockService.allIndustryDailyRange(start, end));
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
        return ApiResponse.ok(stockService.industryProsperity(tradeDate));
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
        return ApiResponse.ok(stockService.industryProsperityRange(start, end, topN));
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
