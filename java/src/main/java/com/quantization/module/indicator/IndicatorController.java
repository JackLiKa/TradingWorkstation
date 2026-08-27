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
        IndicatorConfig defaults = IndicatorConfig.defaults();
        IndicatorConfigDto dto = request.config();
        IndicatorConfig config = (dto == null) ? defaults : mergeConfig(dto, defaults);
        IndicatorSeries series = engine.buildSeries(request.records(), config);
        return ApiResponse.ok(IndicatorSeriesDto.from(series));
    }

    /** 將請求 DTO 與默認值合併：DTO 中非 null 的字段覆蓋默認值。 */
    private static IndicatorConfig mergeConfig(IndicatorConfigDto dto, IndicatorConfig defaults) {
        return new IndicatorConfig(
                dto.showMa() != null ? dto.showMa() : defaults.showMa(),
                dto.maPeriods() != null ? dto.maPeriods() : defaults.maPeriods(),
                dto.showBoll() != null ? dto.showBoll() : defaults.showBoll(),
                dto.showMacd() != null ? dto.showMacd() : defaults.showMacd(),
                dto.showKdj() != null ? dto.showKdj() : defaults.showKdj(),
                dto.bollPeriod() != null ? dto.bollPeriod() : defaults.bollPeriod(),
                dto.bollStd() != null ? dto.bollStd() : defaults.bollStd(),
                dto.macdFastPeriod() != null ? dto.macdFastPeriod() : defaults.macdFastPeriod(),
                dto.macdSlowPeriod() != null ? dto.macdSlowPeriod() : defaults.macdSlowPeriod(),
                dto.macdSignalPeriod() != null ? dto.macdSignalPeriod() : defaults.macdSignalPeriod(),
                dto.kdjPeriod() != null ? dto.kdjPeriod() : defaults.kdjPeriod(),
                dto.kdjKSmoothing() != null ? dto.kdjKSmoothing() : defaults.kdjKSmoothing(),
                dto.kdjDSmoothing() != null ? dto.kdjDSmoothing() : defaults.kdjDSmoothing()
        );
    }

    public record IndicatorComputeRequest(List<com.quantization.module.stock.StockDaily> records,
                                          IndicatorConfigDto config) {
    }
}
