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
import org.springframework.web.bind.annotation.RequestParam;
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
     * 运行回测并自动保存结果到数据库（source=auto）。
     * 用于前端「回测后自动保存」功能，供 AI 优化策略参考。
     *
     * <p>注意：自 {@code runBacktest} 改为自动落库后，此端点与 {@code /run} 行为等价，
     * 保留端点路径以维持 API 兼容性。
     *
     * @param request 回测请求（含选股条件和回测配置）
     * @return 回测结果（已自动保存到数据库）
     */
    @Operation(summary = "运行回测并自动保存")
    @PostMapping("/run-and-save")
    public ApiResponse<BacktestResultDto> runAndSave(@Valid @RequestBody BacktestRequestDto request) {
        // runBacktest 已内置自动落库（source=auto），此处直接复用
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
     * 获取最近 N 次回测记录（按创建时间倒序，source=auto）。
     *
     * @param limit 返回记录数上限（默认 20）
     * @return 策略摘要列表
     */
    @Operation(summary = "最近回测记录")
    @GetMapping("/recent")
    public ApiResponse<List<SavedStrategySummaryDto>> listRecentRuns(
            @RequestParam(defaultValue = "20") int limit) {
        return ApiResponse.ok(backtestService.listRecentRuns(limit));
    }

    /**
     * 获取已保存策略列表。
     *
     * @return 策略摘要列表（按创建时间倒序）
     */
    @Operation(summary = "策略列表")
    @GetMapping("/strategies")
    public ApiResponse<List<SavedStrategySummaryDto>> listStrategies(
            @RequestParam(required = false) String source) {
        return ApiResponse.ok(strategyService.list(source));
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
