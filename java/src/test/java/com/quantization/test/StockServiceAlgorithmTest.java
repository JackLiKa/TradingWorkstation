package com.quantization.test;

import com.quantization.config.properties.AppProperties;
import com.quantization.module.forecast.ForecastService;
import com.quantization.module.industry.IndustryService;
import com.quantization.module.stock.IndustryDailyEntity;
import com.quantization.module.stock.IndustryDailyRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

/**
 * 行業服務與預測服務關鍵算法測試：
 * - C5: 線性回歸除零防護（常數輸入時 denominator=0）— 測 ForecastService
 * - C1: 景氣度公式一致性（computeProsperityMap 與 industryProsperity 使用相同廣度公式）— 測 IndustryService
 */
@DisplayName("行業/預測服務算法修復驗證")
class StockServiceAlgorithmTest {

    /** 構建默認 AppProperties（adaptive-weights=false，保持固定權重兼容行為）。 */
    private static AppProperties defaultAppProperties() {
        return new AppProperties();
    }

    // ===== C5: 線性回歸除零（ForecastService）=====

    @Test
    @DisplayName("forecastLinearRegression 常數輸入不拋異常，返回均值水平預測")
    void forecastLinearRegression_constantInput_noDivideByZero() throws Exception {
        ForecastService service = new ForecastService(mock(IndustryDailyRepository.class), defaultAppProperties());
        Method method = ForecastService.class.getDeclaredMethod("forecastLinearRegression", double[].class, int.class);
        method.setAccessible(true);

        double[] constantData = {50.0, 50.0, 50.0, 50.0, 50.0};
        double[] forecast = (double[]) method.invoke(service, constantData, 3);

        assertThat(forecast).hasSize(3);
        // 常數序列預測應為均值 50.0，不拋除零異常
        for (double v : forecast) {
            assertThat(v).isCloseTo(50.0, org.assertj.core.api.Assertions.within(0.01));
        }
    }

    @Test
    @DisplayName("forecastLinearRegression 正常趨勢輸入返回合理預測")
    void forecastLinearRegression_trendInput_returnsForecast() throws Exception {
        ForecastService service = new ForecastService(mock(IndustryDailyRepository.class), defaultAppProperties());
        Method method = ForecastService.class.getDeclaredMethod("forecastLinearRegression", double[].class, int.class);
        method.setAccessible(true);

        double[] trendData = {10.0, 20.0, 30.0, 40.0, 50.0};
        double[] forecast = (double[]) method.invoke(service, trendData, 2);

        assertThat(forecast).hasSize(2);
        // 線性遞增趨勢，預測值應大於最後一個值
        assertThat(forecast[0]).isGreaterThan(50.0);
        assertThat(forecast[1]).isGreaterThan(forecast[0]);
    }

    // ===== C1: 景氣度公式一致性（IndustryService）=====

    @Test
    @DisplayName("computeProsperityMap 廣度公式與 industryProsperity 一致（rising/total*100）")
    void computeProsperityMap_breadthFormula_matchesIndustryProsperity() throws Exception {
        IndustryService service = new IndustryService(mock(IndustryDailyRepository.class));

        IndustryDailyEntity entity = new IndustryDailyEntity();
        entity.setTradeDate(LocalDate.of(2026, 1, 1));
        entity.setIndustry("測試行業");
        entity.setAvgPctChg(new BigDecimal("2.0"));
        entity.setTotalAmount(new BigDecimal("1000000"));
        entity.setAvgTurn(new BigDecimal("1.5"));
        entity.setRisingCount(30);
        entity.setFallingCount(10);

        List<IndustryDailyEntity> entities = List.of(entity);

        Method method = IndustryService.class.getDeclaredMethod("computeProsperityMap", List.class);
        method.setAccessible(true);

        @SuppressWarnings("unchecked")
        Map<String, Double> result = (Map<String, Double>) method.invoke(service, entities);

        // 單一行業時，所有 normalize 維度的 min=max，normalize 返回 50.0（中間分）
        // 廣度 = rising/(rising+falling)*100 = 30/40*100 = 75.0
        // 單一行業時 breadthMin=breadthMax=75.0，normalize(75, 75, 75) = 50.0
        assertThat(result).containsKey("測試行業");
        double prosperity = result.get("測試行業");
        // prosperity = 0.35*50 + 0.25*50 + 0.20*50 + 0.20*50 = 50.0（單一行業所有維度 min=max）
        assertThat(prosperity).isCloseTo(50.0, org.assertj.core.api.Assertions.within(0.01));
    }

    @Test
    @DisplayName("computeProsperityMap 多行業時廣度按 per-entity rising/total 計算")
    void computeProsperityMap_multipleIndustries_perEntityBreadth() throws Exception {
        IndustryService service = new IndustryService(mock(IndustryDailyRepository.class));

        IndustryDailyEntity e1 = new IndustryDailyEntity();
        e1.setTradeDate(LocalDate.of(2026, 1, 1));
        e1.setIndustry("行業A");
        e1.setAvgPctChg(new BigDecimal("1.0"));
        e1.setTotalAmount(new BigDecimal("500000"));
        e1.setAvgTurn(new BigDecimal("1.0"));
        e1.setRisingCount(40);
        e1.setFallingCount(10);

        IndustryDailyEntity e2 = new IndustryDailyEntity();
        e2.setTradeDate(LocalDate.of(2026, 1, 1));
        e2.setIndustry("行業B");
        e2.setAvgPctChg(new BigDecimal("3.0"));
        e2.setTotalAmount(new BigDecimal("2000000"));
        e2.setAvgTurn(new BigDecimal("2.0"));
        e2.setRisingCount(10);
        e2.setFallingCount(30);

        List<IndustryDailyEntity> entities = List.of(e1, e2);

        Method method = IndustryService.class.getDeclaredMethod("computeProsperityMap", List.class);
        method.setAccessible(true);

        @SuppressWarnings("unchecked")
        Map<String, Double> result = (Map<String, Double>) method.invoke(service, entities);

        assertThat(result).hasSize(2);
        // 驗證廣度按 per-entity rising/total*100 計算：
        // 行業A 廣度 = 40/50*100 = 80，行業B 廣度 = 10/40*100 = 25
        // 行業A 在動量/資金/活躍三維都是 min（0 分），只有廣度是 max（100 分）
        // prosperity_A = 0.35*0 + 0.25*0 + 0.20*0 + 0.20*100 = 20.0
        // prosperity_B = 0.35*100 + 0.25*100 + 0.20*100 + 0.20*0 = 80.0
        // 關鍵：若用舊公式（全局 breadthBase），廣度值會不同，prosperity 也不同
        assertThat(result.get("行業A")).isCloseTo(20.0, org.assertj.core.api.Assertions.within(0.1));
        assertThat(result.get("行業B")).isCloseTo(80.0, org.assertj.core.api.Assertions.within(0.1));
    }
}
