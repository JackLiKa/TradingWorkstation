package com.quantization.module.stock;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.stock.dto.HotSymbolDto;
import com.quantization.module.stock.dto.SearchResultDto;
import com.quantization.module.stock.dto.StockDailyDto;
import com.quantization.module.stock.dto.StockDailyQueryDto;
import com.quantization.module.stock.dto.StockIndustryDto;
import com.quantization.module.stock.dto.StockSuggestionDto;
import com.quantization.module.stock.dto.SummaryMetricsDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;

/**
 * 行情 Controller，提供汇总指标、日线查询、波动榜、搜索建议和行业分类等接口。
 */
@Tag(name = "行情 stock")
@RestController
@RequestMapping("/api/stock")
public class StockController {

    private final StockService stockService;
    private final StockIndustryRepository industryRepository;

    public StockController(StockService stockService, StockIndustryRepository industryRepository) {
        this.stockService = stockService;
        this.industryRepository = industryRepository;
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
     * 搜索建議（自動補全），根據用戶輸入的部分代碼返回最新交易日匹配的股票。
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
     * @param code     股票代碼（可選）
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
}
