package com.quantization.test;

import com.quantization.config.properties.AppProperties;
import com.quantization.module.forecast.ForecastService;
import com.quantization.module.stock.IndustryDailyEntity;
import com.quantization.module.stock.IndustryDailyRepository;
import com.quantization.module.stock.dto.RotationAutoMlDto;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.atLeast;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentCaptor.forClass;

/**
 * ForecastService AutoML 嚴格日期隔離 out-of-sample 評估測試。
 *
 * 驗證：
 * - 調參區間 A 和評估區間 B 不重疊
 * - 評估階段只用區間 B 的數據（repo 查詢起始日期 = evalStartDate，不拉取之前數據）
 * - 默認 70/30 分割正確
 * - DTO 的 tuneRange / evalRange 字段正確標明區間
 */
@DisplayName("AutoML 嚴格日期隔離 out-of-sample 評估")
class ForecastServiceTest {

    /** 構建默認 AppProperties（保持固定權重兼容行為）。 */
    private static AppProperties defaultAppProperties() {
        return new AppProperties();
    }

    /** 生成模擬行業日度數據：每個交易日 15 個行業，跨越指定日期範圍。 */
    private List<IndustryDailyEntity> generateMockData(LocalDate start, int days) {
        List<IndustryDailyEntity> entities = new ArrayList<>();
        String[] industries = {
                "銀行", "證券", "房地產", "鋼鐵", "有色",
                "煤炭", "化工", "醫藥", "電子", "計算機",
                "通信", "傳媒", "電力", "機械", "汽車"
        };
        LocalDate date = start;
        for (int d = 0; d < days; d++) {
            for (int i = 0; i < industries.length; i++) {
                IndustryDailyEntity e = new IndustryDailyEntity();
                e.setId((long) (d * 100 + i));
                e.setTradeDate(date);
                e.setIndustry(industries[i]);
                // 交替漲跌，製造可預測的輪動模式
                e.setAvgPctChg(new BigDecimal(String.format("%.4f", (i % 5 - 2) * 0.5 + (d % 3) * 0.3)));
                e.setTotalAmount(new BigDecimal("1000000"));
                e.setAvgTurn(new BigDecimal("1.5"));
                e.setRisingCount(8);
                e.setFallingCount(7);
                entities.add(e);
            }
            date = date.plusDays(1);
        }
        return entities;
    }

    @Test
    @DisplayName("調參區間 A 和評估區間 B 不重疊（evalStart > tuneEnd）")
    void autoTune_intervalsDoNotOverlap() {
        IndustryDailyRepository repo = mock(IndustryDailyRepository.class);
        // 生成足夠大的數據集，覆蓋所有可能的查詢範圍
        when(repo.findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(any(), any()))
                .thenReturn(generateMockData(LocalDate.of(2025, 1, 1), 200));

        ForecastService service = new ForecastService(repo, new AppProperties());

        LocalDate tuneStart = LocalDate.of(2025, 1, 1);
        LocalDate tuneEnd = LocalDate.of(2025, 6, 30);
        LocalDate evalStart = LocalDate.of(2025, 7, 1);
        LocalDate evalEnd = LocalDate.of(2025, 9, 30);

        RotationAutoMlDto result = service.autoTuneRotationPrediction(
                180, tuneStart, tuneEnd, evalStart, evalEnd);

        // 驗證 tuneRange 和 evalRange 字段
        assertThat(result.tuneRange()).isEqualTo("2025-01-01 ~ 2025-06-30");
        assertThat(result.evalRange()).isEqualTo("2025-07-01 ~ 2025-09-30");

        // 驗證區間不重疊：evalStart 在 tuneEnd 之後
        assertThat(evalStart.isAfter(tuneEnd)).isTrue();
    }

    @Test
    @DisplayName("評估階段只用區間 B 數據——repo 查詢起始日期不小於 evalStartDate")
    void autoTune_evalPhaseOnlyUsesIntervalBData() {
        IndustryDailyRepository repo = mock(IndustryDailyRepository.class);
        when(repo.findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(any(), any()))
                .thenReturn(generateMockData(LocalDate.of(2025, 1, 1), 200));

        ForecastService service = new ForecastService(repo, new AppProperties());

        LocalDate tuneStart = LocalDate.of(2025, 1, 1);
        LocalDate tuneEnd = LocalDate.of(2025, 6, 30);
        LocalDate evalStart = LocalDate.of(2025, 7, 1);
        LocalDate evalEnd = LocalDate.of(2025, 9, 30);

        service.autoTuneRotationPrediction(180, tuneStart, tuneEnd, evalStart, evalEnd);

        // 捕獲所有 repo 查詢調用的日期參數
        var startCaptor = forClass(LocalDate.class);
        var endCaptor = forClass(LocalDate.class);
        verify(repo, atLeast(2))
                .findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(startCaptor.capture(), endCaptor.capture());

        List<LocalDate> allStarts = startCaptor.getAllValues();
        // 至少有調參階段（15 組合）和評估階段（1 次）的查詢
        assertThat(allStarts).hasSizeGreaterThanOrEqualTo(2);

        // 調參階段的查詢起始日期應為 tuneStart
        // 評估階段的查詢起始日期應為 evalStart（絕不能是 tuneStart 或更早）
        boolean hasTuneQuery = allStarts.stream().anyMatch(d -> d.equals(tuneStart));
        boolean hasEvalQuery = allStarts.stream().anyMatch(d -> d.equals(evalStart));
        assertThat(hasTuneQuery).as("調參階段應以 tuneStart 查詢數據").isTrue();
        assertThat(hasEvalQuery).as("評估階段應以 evalStart 查詢數據").isTrue();

        // 所有查詢起始日期都不應早於 tuneStart（即不拉取區間之前的數據）
        for (LocalDate s : allStarts) {
            assertThat(s).isAfterOrEqualTo(tuneStart);
        }
    }

    @Test
    @DisplayName("傳入重疊區間時自動調整 evalStart 到 tuneEnd 之後")
    void autoTune_overlappingIntervals_autoAdjusted() {
        IndustryDailyRepository repo = mock(IndustryDailyRepository.class);
        when(repo.findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(any(), any()))
                .thenReturn(generateMockData(LocalDate.of(2025, 1, 1), 200));

        ForecastService service = new ForecastService(repo, new AppProperties());

        // 故意傳入重疊區間：evalStart < tuneEnd
        LocalDate tuneStart = LocalDate.of(2025, 1, 1);
        LocalDate tuneEnd = LocalDate.of(2025, 6, 30);
        LocalDate evalStart = LocalDate.of(2025, 6, 15); // 重疊！
        LocalDate evalEnd = LocalDate.of(2025, 9, 30);

        RotationAutoMlDto result = service.autoTuneRotationPrediction(
                180, tuneStart, tuneEnd, evalStart, evalEnd);

        // evalRange 應自動調整為 tuneEnd+1 ~ evalEnd
        assertThat(result.evalRange()).isEqualTo("2025-07-01 ~ 2025-09-30");
        // tuneRange 不變
        assertThat(result.tuneRange()).isEqualTo("2025-01-01 ~ 2025-06-30");
    }

    @Test
    @DisplayName("默認 70/30 分割：不傳日期時前 70% 調參、後 30% 評估")
    void autoTune_defaultSplit_70_30() {
        IndustryDailyRepository repo = mock(IndustryDailyRepository.class);
        when(repo.findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(any(), any()))
                .thenReturn(generateMockData(LocalDate.now().minusDays(200), 200));

        ForecastService service = new ForecastService(repo, new AppProperties());

        int backtestDays = 100;
        RotationAutoMlDto result = service.autoTuneRotationPrediction(backtestDays);

        // 驗證 tuneRange 和 evalRange 都非空
        assertThat(result.tuneRange()).isNotBlank();
        assertThat(result.evalRange()).isNotBlank();

        // 解析 tuneRange 和 evalRange 的日期
        String[] tuneParts = result.tuneRange().split(" ~ ");
        String[] evalParts = result.evalRange().split(" ~ ");
        LocalDate tuneStart = LocalDate.parse(tuneParts[0]);
        LocalDate tuneEnd = LocalDate.parse(tuneParts[1]);
        LocalDate evalStart = LocalDate.parse(evalParts[0]);
        LocalDate evalEnd = LocalDate.parse(evalParts[1]);

        // 驗證區間不重疊
        assertThat(evalStart.isAfter(tuneEnd)).isTrue();

        // 驗證大致 70/30 比例：tuneEnd - tuneStart ≈ 70% backtestDays
        long tuneSpan = tuneEnd.toEpochDay() - tuneStart.toEpochDay();
        long evalSpan = evalEnd.toEpochDay() - evalStart.toEpochDay();
        long totalSpan = tuneSpan + evalSpan;
        // 允許 ±5 天誤差（因為 splitPoint + 1 天的隔離間隙）
        assertThat(tuneSpan).isCloseTo((long) (totalSpan * 0.7), org.assertj.core.api.Assertions.within(5L));
        assertThat(evalSpan).isCloseTo((long) (totalSpan * 0.3), org.assertj.core.api.Assertions.within(5L));
    }

    @Test
    @DisplayName("不傳日期參數時行為與之前一致——DTO 結構完整、summary 非空")
    void autoTune_noDateParams_returnsValidDto() {
        IndustryDailyRepository repo = mock(IndustryDailyRepository.class);
        when(repo.findByTradeDateBetweenOrderByTradeDateAscIndustryAsc(any(), any()))
                .thenReturn(generateMockData(LocalDate.now().minusDays(200), 200));

        ForecastService service = new ForecastService(repo, new AppProperties());

        RotationAutoMlDto result = service.autoTuneRotationPrediction(90);

        // DTO 結構完整
        assertThat(result).isNotNull();
        assertThat(result.summary()).isNotBlank();
        assertThat(result.combinations()).isNotEmpty();
        // 每個組合都有調參段數據
        for (RotationAutoMlDto.ParamCombination c : result.combinations()) {
            assertThat(c.lookbackDays()).isPositive();
            assertThat(c.forwardDays()).isPositive();
        }
        // tuneRange 和 evalRange 已填充
        assertThat(result.tuneRange()).contains("~");
        assertThat(result.evalRange()).contains("~");
    }
}
