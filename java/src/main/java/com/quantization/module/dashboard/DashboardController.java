package com.quantization.module.dashboard;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.dashboard.dto.DashboardSnapshotDto;
import com.quantization.module.stock.dto.SummaryMetricsDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;

/**
 * 仪表盘 Controller，提供总览快照和汇总指标接口。
 */
@Tag(name = "总览 dashboard")
@RestController
@RequestMapping("/api/dashboard")
public class DashboardController {

    private final DashboardService dashboardService;

    public DashboardController(DashboardService dashboardService) {
        this.dashboardService = dashboardService;
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
}
