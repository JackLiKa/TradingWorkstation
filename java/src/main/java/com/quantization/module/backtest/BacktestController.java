package com.quantization.module.backtest;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.backtest.dto.BacktestRequestDto;
import com.quantization.module.backtest.dto.BacktestResultDto;
import com.quantization.module.backtest.dto.SaveStrategyDto;
import com.quantization.module.backtest.dto.SavedStrategyDetailDto;
import com.quantization.module.backtest.dto.SavedStrategySummaryDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 回测 Controller，提供策略回测运行与已保存策略的 CRUD 接口。
 */
@Tag(name = "回测 backtest")
@RestController
@RequestMapping("/api/backtest")
public class BacktestController {

    private final BacktestService backtestService;
    private final BacktestStrategyService strategyService;

    public BacktestController(BacktestService backtestService, BacktestStrategyService strategyService) {
        this.backtestService = backtestService;
        this.strategyService = strategyService;
    }

    /**
     * 运行回测。
     *
     * @param request 回测请求（含选股条件和回测配置）
     * @return 回测结果
     */
    @Operation(summary = "运行回测")
    @PostMapping("/run")
    public ApiResponse<BacktestResultDto> run(@Valid @RequestBody BacktestRequestDto request) {
        return ApiResponse.ok(backtestService.runBacktest(request));
    }

    /**
     * 保存回测策略。
     *
     * @param dto 策略保存请求
     * @return 已保存的策略详情
     */
    @Operation(summary = "保存策略")
    @PostMapping("/strategies")
    public ApiResponse<SavedStrategyDetailDto> saveStrategy(@RequestBody SaveStrategyDto dto) {
        return ApiResponse.ok(strategyService.save(dto));
    }

    /**
     * 获取已保存策略列表。
     *
     * @return 策略摘要列表（按创建时间倒序）
     */
    @Operation(summary = "策略列表")
    @GetMapping("/strategies")
    public ApiResponse<List<SavedStrategySummaryDto>> listStrategies() {
        return ApiResponse.ok(strategyService.list());
    }

    /**
     * 获取指定策略详情。
     *
     * @param id 策略 ID
     * @return 策略详情（含配置和可选的完整结果）
     */
    @Operation(summary = "策略详情")
    @GetMapping("/strategies/{id}")
    public ApiResponse<SavedStrategyDetailDto> getStrategy(@PathVariable Long id) {
        return ApiResponse.ok(strategyService.getById(id));
    }

    /**
     * 删除指定策略。
     *
     * @param id 策略 ID
     * @return 空数据响应
     */
    @Operation(summary = "删除策略")
    @DeleteMapping("/strategies/{id}")
    public ApiResponse<Void> deleteStrategy(@PathVariable Long id) {
        strategyService.delete(id);
        return ApiResponse.ok(null);
    }
}
