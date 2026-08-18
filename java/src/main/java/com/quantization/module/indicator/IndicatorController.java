package com.quantization.module.indicator;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.indicator.dto.IndicatorConfigDto;
import com.quantization.module.indicator.dto.IndicatorSeriesDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 技术指标 Controller，提供指标全序列计算接口（供前端图表叠加使用）。
 */
@Tag(name = "指标 indicator")
@RestController
@RequestMapping("/api/indicator")
public class IndicatorController {

    private final IndicatorEngine engine;

    public IndicatorController(IndicatorEngine engine) {
        this.engine = engine;
    }

    /**
     * 计算指标全序列（MA、BOLL、MACD、KDJ、RSI 等），供图表叠加。
     *
     * @param request 包含行情记录和指标配置的请求
     * @return 指标序列 DTO
     */
    @Operation(summary = "计算指标全序列（图表叠加用）")
    @PostMapping("/compute")
    public ApiResponse<IndicatorSeriesDto> compute(@RequestBody IndicatorComputeRequest request) {
        IndicatorConfig config = IndicatorConfig.defaults();
        IndicatorSeries series = engine.buildSeries(request.records(), config);
        return ApiResponse.ok(IndicatorSeriesDto.from(series));
    }

    public record IndicatorComputeRequest(List<com.quantization.module.stock.StockDaily> records,
                                          IndicatorConfigDto config) {
    }
}
