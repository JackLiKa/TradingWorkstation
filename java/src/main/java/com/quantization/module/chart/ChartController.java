package com.quantization.module.chart;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.chart.dto.CandlestickDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;

/**
 * K线图 Controller，提供初始批次和更早历史批次的 K线数据加载接口。
 */
@Tag(name = "K线 chart")
@RestController
@RequestMapping("/api/chart")
public class ChartController {

    private final ChartService chartService;

    public ChartController(ChartService chartService) {
        this.chartService = chartService;
    }

    /**
     * 加载 K线初始批次（含技术指标序列）。
     *
     * @param code       股票代码
     * @param adjustflag 复权方式（默认 3 = 不复权）
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @return K线数据 DTO（含 OHLCV 记录和指标序列）
     */
    @Operation(summary = "K线初始批次（含指标序列）")
    @GetMapping("/candlestick")
    public ApiResponse<CandlestickDto> candlestick(
            @RequestParam String code,
            @RequestParam(required = false, defaultValue = "3") int adjustflag,
            @RequestParam(required = false) LocalDate startDate,
            @RequestParam(required = false) LocalDate endDate) {
        return ApiResponse.ok(chartService.loadCandlestick(code, adjustflag, startDate, endDate));
    }

    /**
     * 加载更早历史批次（用于"加载更多"功能）。
     *
     * @param code       股票代码
     * @param adjustflag 复权方式（默认 3 = 不复权）
     * @param beforeDate 截止日期（加载此日期之前的数据）
     * @param startDate  起始日期（可选）
     * @param endDate    结束日期（可选）
     * @return K线数据 DTO
     */
    @Operation(summary = "更早历史批次")
    @GetMapping("/candlestick/older")
    public ApiResponse<CandlestickDto> older(
            @RequestParam String code,
            @RequestParam(required = false, defaultValue = "3") int adjustflag,
            @RequestParam LocalDate beforeDate,
            @RequestParam(required = false) LocalDate startDate,
            @RequestParam(required = false) LocalDate endDate) {
        return ApiResponse.ok(chartService.loadOlder(code, adjustflag, beforeDate, startDate, endDate));
    }
}
