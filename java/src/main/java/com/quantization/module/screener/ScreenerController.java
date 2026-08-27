package com.quantization.module.screener;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import com.quantization.module.screener.dto.ScreenerResultDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 选股 Controller，提供运行选股筛选的接口。
 */
@Tag(name = "选股 screener")
@RestController
@RequestMapping("/api/screener")
public class ScreenerController {

    private final ScreenerService screenerService;

    public ScreenerController(ScreenerService screenerService) {
        this.screenerService = screenerService;
    }

    /**
     * 运行选股筛选。
     *
     * @param criteria 选股条件
     * @return 选股结果（含命中股票列表和摘要日志）
     */
    @Operation(summary = "运行选股")
    @PostMapping("/run")
    public ApiResponse<ScreenerResultDto> run(@Valid @RequestBody ScreenerCriteriaDto criteria) {
        return ApiResponse.ok(screenerService.runScreener(criteria));
    }
}
