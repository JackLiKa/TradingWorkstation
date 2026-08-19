package com.quantization.module.aicalllog;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.aicalllog.dto.AiCallLogDto;
import com.quantization.module.aicalllog.dto.AiCallLogRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.data.domain.Page;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * AI 調用日誌 Controller — 提供 Agent Dashboard 所需的 API 端點。
 */
@Tag(name = "AI 調用日誌 aicalllog")
@RestController
@RequestMapping("/api/aicalllog")
public class AiCallLogController {

    private final AiCallLogService service;

    public AiCallLogController(AiCallLogService service) {
        this.service = service;
    }

    /** 記錄一條 AI 調用日誌（Agent 服務調用） */
    @Operation(summary = "記錄 AI 調用日誌")
    @PostMapping("/log")
    public ApiResponse<AiCallLogDto> log(@RequestBody AiCallLogRequest request) {
        return ApiResponse.ok(service.log(request));
    }

    /** 分頁查詢全部日誌 */
    @Operation(summary = "分頁查詢 AI 調用日誌")
    @GetMapping
    public ApiResponse<Page<AiCallLogDto>> findAll(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.ok(service.findAll(page, size));
    }

    /** 按階段分頁查詢 */
    @Operation(summary = "按階段查詢 AI 調用日誌")
    @GetMapping("/stage/{stageName}")
    public ApiResponse<Page<AiCallLogDto>> findByStage(
            @PathVariable String stageName,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.ok(service.findByStage(stageName, page, size));
    }

    /** 查詢某次迭代的全部階段日誌（調用鏈） */
    @Operation(summary = "查詢某次迭代的調用鏈")
    @GetMapping("/iteration/{iteration}")
    public ApiResponse<List<AiCallLogDto>> findByIteration(@PathVariable int iteration) {
        return ApiResponse.ok(service.findByIteration(iteration));
    }

    /** 查詢最近 N 條日誌 */
    @Operation(summary = "查詢最近日誌")
    @GetMapping("/recent")
    public ApiResponse<List<AiCallLogDto>> findRecent(@RequestParam(defaultValue = "10") int limit) {
        return ApiResponse.ok(service.findRecent(limit));
    }

    /** 評分趨勢數據（用於前端圖表） */
    @Operation(summary = "評分趨勢數據")
    @GetMapping("/score-trend")
    public ApiResponse<Map<String, Object>> scoreTrend() {
        return ApiResponse.ok(service.scoreTrend());
    }
}
