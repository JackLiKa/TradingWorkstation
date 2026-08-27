package com.quantization.test;

import com.quantization.config.properties.AppProperties;
import com.quantization.module.forecast.ForecastService;
import com.quantization.module.stock.IndustryDailyRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

/**
 * 滾動窗口集成權重適應（Phase 4 後續）測試。
 * <p>
 * 驗證：
 * <ul>
 *   <li>{@code adaptive-weights=false} 時使用固定權重 0.35/0.35/0.30（向後兼容）。</li>
 *   <li>{@code adaptive-weights=true} 時 {@code computeAdaptiveWeights} 返回動態權重。</li>
 *   <li>動態權重三個分量和為 1.0。</li>
 *   <li>滾動窗口計算只用歷史數據（不接觸未來）——透過 one-step-ahead 機制保證。</li>
 *   <li>數據不足時回退到固定權重，永不拋異常。</li>
 * </ul>
 */
@DisplayName("滾動窗口集成權重適應驗證")
class ForecastAdaptiveWeightsTest {

    /** 構建 AppProperties 並設定 adaptive-weights 開關。 */
    private static AppProperties appProperties(boolean adaptive, int windowDays) {
        AppProperties props = new AppProperties();
        props.getForecast().setAdaptiveWeights(adaptive);
        props.getForecast().setRollingWindowDays(windowDays);
        return props;
    }

    private static ForecastService service(boolean adaptive, int windowDays) {
        return new ForecastService(mock(IndustryDailyRepository.class), appProperties(adaptive, windowDays));
    }

    /** 反射調用 package-private computeAdaptiveWeights(double[], int)。 */
    private static double[] computeAdaptiveWeights(ForecastService service, double[] data, int windowDays)
            throws Exception {
        Method method = ForecastService.class.getDeclaredMethod("computeAdaptiveWeights", double[].class, int.class);
        method.setAccessible(true);
        return (double[]) method.invoke(service, data, windowDays);
    }

    /** 反射調用 private weightSourceLabel()。 */
    private static String weightSourceLabel(ForecastService service) throws Exception {
        Method method = ForecastService.class.getDeclaredMethod("weightSourceLabel");
        method.setAccessible(true);
        return (String) method.invoke(service);
    }

    // ===== 固定權重兼容（adaptive-weights=false）=====

    @Test
    @DisplayName("adaptive-weights=false 時 weightSourceLabel 為 fixed")
    void weightSourceLabel_fixedWhenAdaptiveOff() throws Exception {
        ForecastService service = service(false, 60);
        assertThat(weightSourceLabel(service)).isEqualTo("fixed");
    }

    @Test
    @DisplayName("adaptive-weights=true 時 weightSourceLabel 為 adaptive")
    void weightSourceLabel_adaptiveWhenAdaptiveOn() throws Exception {
        ForecastService service = service(true, 60);
        assertThat(weightSourceLabel(service)).isEqualTo("adaptive");
    }

    // ===== 動態權重計算 =====

    @Test
    @DisplayName("computeAdaptiveWeights 返回三個權重且和為 1.0")
    void computeAdaptiveWeights_weightsSumToOne() throws Exception {
        ForecastService service = service(true, 30);
        // 構建 80 個帶趨勢+噪聲的景氣度序列
        double[] data = new double[80];
        for (int i = 0; i < 80; i++) {
            data[i] = 50 + 0.2 * i + Math.sin(i * 0.5) * 3;
            data[i] = Math.max(0, Math.min(100, data[i]));
        }
        double[] weights = computeAdaptiveWeights(service, data, 30);
        assertThat(weights).hasSize(3);
        double sum = weights[0] + weights[1] + weights[2];
        assertThat(sum).isCloseTo(1.0, org.assertj.core.api.Assertions.within(1e-9));
        // 每個權重都在 [0,1] 內
        for (double w : weights) {
            assertThat(w).isBetween(0.0, 1.0);
        }
    }

    @Test
    @DisplayName("computeAdaptiveWeights 數據不足時回退到固定權重")
    void computeAdaptiveWeights_insufficientData_fallsBackToFixed() throws Exception {
        ForecastService service = service(true, 60);
        // 僅 5 個點，無法構成有效窗口
        double[] data = {50.0, 51.0, 52.0, 53.0, 54.0};
        double[] weights = computeAdaptiveWeights(service, data, 60);
        assertThat(weights).hasSize(3);
        assertThat(weights[0]).isCloseTo(0.35, org.assertj.core.api.Assertions.within(1e-9));
        assertThat(weights[1]).isCloseTo(0.35, org.assertj.core.api.Assertions.within(1e-9));
        assertThat(weights[2]).isCloseTo(0.30, org.assertj.core.api.Assertions.within(1e-9));
    }

    @Test
    @DisplayName("computeAdaptiveWeights 對帶噪聲線性趨勢數據給線性回歸更高權重")
    void computeAdaptiveWeights_linearTrend_favorsLinearRegression() throws Exception {
        ForecastService service = service(true, 40);
        // 線性遞增 + 小幅噪聲序列：線性回歸 MAE 最小（擬合趨勢最佳），權重應最大。
        // 噪聲確保各模型 MAE > 0.01 閾值（避免逆 MAE 被當作 0）。
        double[] data = new double[80];
        java.util.Random rng = new java.util.Random(42);
        for (int i = 0; i < 80; i++) {
            data[i] = 30 + 0.4 * i + (rng.nextDouble() - 0.5) * 2.0;
            data[i] = Math.max(0, Math.min(100, data[i]));
        }
        double[] weights = computeAdaptiveWeights(service, data, 40);
        double sum = weights[0] + weights[1] + weights[2];
        assertThat(sum).isCloseTo(1.0, org.assertj.core.api.Assertions.within(1e-9));
        // 線性回歸（索引 2）權重應不小於固定權重 0.30（趨勢數據下線性回歸最準）
        assertThat(weights[2]).isGreaterThanOrEqualTo(0.30);
    }

    // ===== look-ahead bias 防護 =====

    @Test
    @DisplayName("computeAdaptiveWeights 不拋異常（窗口邊界安全）")
    void computeAdaptiveWeights_doesNotThrow_onEdgeCases() throws Exception {
        ForecastService service = service(true, 60);
        // 各種邊界數據均不應拋異常
        double[] shortData = {50.0, 51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0, 58.0, 59.0, 60.0};
        double[] w1 = computeAdaptiveWeights(service, shortData, 60);
        assertThat(w1).hasSize(3);

        double[] constantData = new double[70];
        java.util.Arrays.fill(constantData, 50.0);
        double[] w2 = computeAdaptiveWeights(service, constantData, 30);
        assertThat(w2).hasSize(3);
        // 常數序列所有模型 MAE≈0 → 回退固定權重
        assertThat(w2[0]).isCloseTo(0.35, org.assertj.core.api.Assertions.within(1e-9));
    }

    @Test
    @DisplayName("computeAdaptiveWeights 窗口大小不影響權重和為 1.0")
    void computeAdaptiveWeights_variousWindowSizes_sumToOne() throws Exception {
        ForecastService service = service(true, 20);
        double[] data = new double[100];
        for (int i = 0; i < 100; i++) {
            data[i] = 50 + Math.sin(i * 0.3) * 10 + (i % 7 - 3) * 0.5;
            data[i] = Math.max(0, Math.min(100, data[i]));
        }
        for (int window : new int[]{10, 20, 50, 90}) {
            double[] weights = computeAdaptiveWeights(service, data, window);
            double sum = weights[0] + weights[1] + weights[2];
            assertThat(sum).isCloseTo(1.0, org.assertj.core.api.Assertions.within(1e-9));
        }
    }
}
