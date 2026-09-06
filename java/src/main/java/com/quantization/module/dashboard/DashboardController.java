package com.quantization.module.dashboard;

import com.quantization.common.api.ApiResponse;
import com.quantization.common.api.PaginatedResponse;
import com.quantization.module.dashboard.dto.DashboardSnapshotDto;
import com.quantization.module.stock.StockIndustryRepository;
import com.quantization.module.stock.dto.StockCodeNameDto;
import com.quantization.module.stock.dto.SummaryMetricsDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.Arrays;
import java.util.List;

/**
 * 仪表盘 Controller，提供总览快照和汇总指标接口。
 */
@Tag(name = "总览 dashboard")
@RestController
@RequestMapping("/api/dashboard")
public class DashboardController {

    private final DashboardService dashboardService;
    private final StockIndustryRepository stockIndustryRepository;

    public DashboardController(DashboardService dashboardService, StockIndustryRepository stockIndustryRepository) {
        this.dashboardService = dashboardService;
        this.stockIndustryRepository = stockIndustryRepository;
    }

    /**
     * 加载仪表盘总览快照（指标卡片 + 表格 + K线 + 波动榜 + 日志）。
     *
     * @param code       股票代码（可选，为空则自动选取）
     * @param adjustflag 复权方式（可选）
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @param limit      返回条数限制（可选）
     * @return 仪表盘快照 DTO
     */
    @Operation(summary = "加载总览（指标+表格+K线+波动+日志）")
    @GetMapping
    public ApiResponse<DashboardSnapshotDto> dashboard(
            @RequestParam(required = false) String code,
            @RequestParam(required = false) Integer adjustflag,
            @RequestParam(required = false) LocalDate startDate,
            @RequestParam(required = false) LocalDate endDate,
            @RequestParam(required = false) Integer limit) {
        return ApiResponse.ok(dashboardService.loadDashboard(code, adjustflag, startDate, endDate, limit));
    }

    /**
     * 获取汇总指标（走缓存，TTL 由配置控制）。
     *
     * @return 汇总指标 DTO
     */
    @Operation(summary = "汇总指标（缓存）")
    @GetMapping("/summary")
    public ApiResponse<SummaryMetricsDto> summary() {
        return ApiResponse.ok(dashboardService.cachedSummary());
    }

    /**
     * 輕量查詢：根據行業分類代碼查詢股票 code+name（投影查詢，不加載完整實體）。
     * <p>
     * 支持多個行業代碼（逗號分隔），如 C38,C37,C36,I64,C39。
     * 每條結果只含 code 和 name，約 30 字節，即使返回 1000 條也只占 30KB 內存。
     * </p>
     *
     * @param industryCodes 行業分類代碼，逗號分隔（如 C38,C37,C36）
     * @param keyword       行業名稱關鍵詞（可選，如「電氣機械」）
     * @return 股票 code+name 列表
     */
    @Operation(summary = "行業股票列表（輕量投影查詢，自動分批）")
    @GetMapping("/industry/stocks")
    public ApiResponse<PaginatedResponse<StockCodeNameDto>> industryStocks(
            @Parameter(description = "行業分類代碼，逗號分隔（如 C38,C37,C36,I64,C39）")
            @RequestParam(required = false) String industryCodes,
            @Parameter(description = "行業名稱關鍵詞（如「電氣機械」），與 industryCodes 二選一")
            @RequestParam(required = false) String keyword,
            @Parameter(description = "偏移量（分批查詢用，默認 0）")
            @RequestParam(required = false, defaultValue = "0") Integer offset) {
        List<StockCodeNameDto> allStocks;
        if (industryCodes != null && !industryCodes.isBlank()) {
            List<String> codes = Arrays.stream(industryCodes.split(","))
                    .map(String::trim)
                    .filter(s -> !s.isEmpty())
                    .toList();
            String p1 = codes.size() > 0 ? codes.get(0) : "";
            String p2 = codes.size() > 1 ? codes.get(1) : "";
            String p3 = codes.size() > 2 ? codes.get(2) : "";
            String p4 = codes.size() > 3 ? codes.get(3) : "";
            String p5 = codes.size() > 4 ? codes.get(4) : "";
            allStocks = stockIndustryRepository.findCodeNameByIndustryClassification(p1, p2, p3, p4, p5);
        } else if (keyword != null && !keyword.isBlank()) {
            allStocks = stockIndustryRepository.findCodeNameByIndustryContaining(keyword);
        } else {
            return ApiResponse.ok(PaginatedResponse.of(List.of(), 0));
        }
        // 智能分批：每批最多 100 條，超過時附加 hasMore 和 message
        return ApiResponse.ok(PaginatedResponse.of(allStocks, offset != null ? offset : 0, 100));
    }
}
