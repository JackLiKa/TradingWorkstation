package com.quantization.module.dailydigest;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.dailydigest.dto.DailyDigestDto;
import com.quantization.module.dailydigest.dto.DailyDigestRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;

/**
 * 當日市場摘要 Controller — 提供摘要的生成、查詢 API。
 */
@Tag(name = "當日市場摘要 dailydigest")
@RestController
@RequestMapping("/api/dailydigest")
public class DailyDigestController {

    private final DailyDigestService service;

    public DailyDigestController(DailyDigestService service) {
        this.service = service;
    }

    /** 保存當日摘要（Agent 服務調用） */
    @Operation(summary = "保存當日市場摘要")
    @PostMapping
    public ApiResponse<DailyDigestDto> save(@RequestBody DailyDigestRequest request) {
        return ApiResponse.ok(service.save(request));
    }

    /** 按交易日查詢摘要 */
    @Operation(summary = "按交易日查詢摘要")
    @GetMapping("/{tradeDate}")
    public ApiResponse<DailyDigestDto> findByDate(@PathVariable String tradeDate) {
        return ApiResponse.ok(service.findByTradeDate(LocalDate.parse(tradeDate)));
    }

    /** 查詢最新摘要 */
    @Operation(summary = "查詢最新摘要")
    @GetMapping("/latest")
    public ApiResponse<DailyDigestDto> findLatest() {
        List<DailyDigestDto> recent = service.findRecent(1);
        return ApiResponse.ok(recent.isEmpty() ? null : recent.get(0));
    }

    /** 查詢最近 N 條摘要 */
    @Operation(summary = "查詢最近摘要")
    @GetMapping("/recent")
    public ApiResponse<List<DailyDigestDto>> findRecent(@RequestParam(defaultValue = "10") int limit) {
        return ApiResponse.ok(service.findRecent(limit));
    }
}
