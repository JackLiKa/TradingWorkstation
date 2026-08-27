package com.quantization.test;

import com.quantization.module.indicator.IndicatorMath;
import com.quantization.module.stock.StockDaily;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

/**
 * IndicatorMath 单元测试 — 验证 Java 移植与原 Python 计算一致。
 * 测试数据由 TestDataBuilder 生成，与 Python test_dashboard_service.py 同源。
 */
@DisplayName("IndicatorMath 指标计算")
class IndicatorMathTest {

    @Nested
    @DisplayName("移动平均 MA")
    class MovingAverageTests {
        @Test
        @DisplayName("数据充足时返回最近 N 天均值（4 位小数）")
        void returnsMeanWhenSufficient() {
            List<Double> values = List.of(10.0, 11.0, 12.0, 13.0, 14.0);
            Double ma5 = IndicatorMath.movingAverage(values, 5);
            assertThat(ma5).isCloseTo(12.0, within(1e-4));
        }

        @Test
        @DisplayName("数据不足时返回 null")
        void returnsNullWhenInsufficient() {
            List<Double> values = List.of(10.0, 11.0, 12.0);
            Double ma5 = IndicatorMath.movingAverage(values, 5);
            assertThat(ma5).isNull();
        }

        @Test
        @DisplayName("180 天合成数据 MA5 与 Python round(mean(values[-5:]),4) 一致")
        void ma5OnSyntheticData() {
            List<StockDaily> records = TestDataBuilder.strongStock();
            List<Double> closes = records.stream().map(StockDaily::closePrice).toList();
            Double ma5 = IndicatorMath.movingAverage(closes, 5);
            // 手动计算最后 5 天均值
            double expected = mean(closes.subList(closes.size() - 5, closes.size()));
            assertThat(ma5).isCloseTo(round(expected, 4), within(1e-4));
        }
    }

    @Nested
    @DisplayName("区间收益 periodReturn")
    class PeriodReturnTests {
        @Test
        @DisplayName("20 日收益 = (close[-1]/close[-21] - 1) * 100")
        void return20Calculation() {
            List<Double> values = Stream.iterate(10.0, v -> v * 1.01).limit(30).toList();
            Double r20 = IndicatorMath.periodReturn(values, 20);
            double expected = (values.get(29) / values.get(9) - 1) * 100;
            assertThat(r20).isCloseTo(round(expected, 4), within(1e-4));
        }

        @Test
        @DisplayName("数据不足返回 null")
        void returnsNullWhenInsufficient() {
            assertThat(IndicatorMath.periodReturn(List.of(1.0, 2.0, 3.0), 5)).isNull();
        }

        @Test
        @DisplayName("基准价为 0 返回 null")
        void returnsNullWhenBaseZero() {
            List<Double> values = List.of(0.0, 1.0, 2.0, 3.0, 4.0, 5.0);
            assertThat(IndicatorMath.periodReturn(values, 5)).isNull();
        }
    }

    @Nested
    @DisplayName("量比 volumeRatio")
    class VolumeRatioTests {
        @Test
        @DisplayName("量比 = 当日成交量 / 前 20 日均量")
        void volumeRatioCalculation() {
            List<StockDaily> records = TestDataBuilder.strongStock();
            Double vr = IndicatorMath.volumeRatio(records, 20);
            assertThat(vr).isNotNull().isGreaterThan(0.0);
        }

        @Test
        @DisplayName("数据不足返回 null")
        void returnsNullWhenInsufficient() {
            List<StockDaily> shortHistory = TestDataBuilder.strongStock().subList(0, 10);
            assertThat(IndicatorMath.volumeRatio(shortHistory, 20)).isNull();
        }
    }

    @Nested
    @DisplayName("振幅 amplitude")
    class AmplitudeTests {
        @Test
        @DisplayName("振幅 = (high - low) / preclose * 100")
        void amplitudeCalculation() {
            StockDaily record = new StockDaily(
                    "sh.600000", java.time.LocalDate.of(2026, 1, 2),
                    9.96, 10.12, 9.88, 10.0, 10.0,
                    1_200_000L, 12_000_000.0, 3,
                    1.0, 1, 0.0, 0
            );
            double amp = IndicatorMath.amplitude(record);
            assertThat(amp).isCloseTo((10.12 - 9.88) / 10.0 * 100, within(1e-4));
        }

        @Test
        @DisplayName("high 或 low 为 null 返回 0")
        void returnsZeroWhenNull() {
            StockDaily record = new StockDaily(
                    "x", java.time.LocalDate.now(),
                    null, null, null, 10.0, 10.0,
                    100L, 1000.0, 3, 1.0, 1, 0.0, 0
            );
            assertThat(IndicatorMath.amplitude(record)).isCloseTo(0.0, within(1e-10));
        }
    }

    @Nested
    @DisplayName("EMA 指数移动平均")
    class EmaTests {
        @Test
        @DisplayName("首值 = 原始值，后续按 multiplier 递推")
        void emaRecursion() {
            List<Double> values = List.of(10.0, 11.0, 12.0, 13.0, 14.0);
            List<Double> ema3 = IndicatorMath.ema(values, 3);
            double multiplier = 2.0 / 4;
            assertThat(ema3.get(0)).isCloseTo(10.0, within(1e-10));
            double expected1 = (11.0 - 10.0) * multiplier + 10.0;
            assertThat(ema3.get(1)).isCloseTo(expected1, within(1e-10));
        }

        @Test
        @DisplayName("null 值传播")
        void emaWithNull() {
            List<Double> values = java.util.Arrays.asList(10.0, null, 12.0);
            List<Double> ema = IndicatorMath.ema(values, 2);
            assertThat(ema.get(0)).isCloseTo(10.0, within(1e-10));
            assertThat(ema.get(1)).isNull();
        }
    }

    @Nested
    @DisplayName("BOLL 布林带")
    class BollTests {
        @Test
        @DisplayName("前 period-1 个值为 null，之后有值")
        void bollNullPrefix() {
            List<Double> closes = Stream.iterate(10.0, v -> v + 0.1).limit(30).toList();
            IndicatorMath.BollSeries boll = IndicatorMath.boll(closes, 20, 2.0);
            assertThat(boll.upper().get(0)).isNull();
            assertThat(boll.upper().get(19)).isNotNull();
            assertThat(boll.middle().get(19)).isNotNull();
            // 上轨 > 中轨 > 下轨
            assertThat(boll.upper().get(29)).isGreaterThan(boll.middle().get(29));
            assertThat(boll.middle().get(29)).isGreaterThan(boll.lower().get(29));
        }
    }

    @Nested
    @DisplayName("MACD")
    class MacdTests {
        @Test
        @DisplayName("DIF = EMA_fast - EMA_slow，HIST = (DIF - DEA) * 2")
        void macdComponents() {
            List<Double> closes = Stream.iterate(10.0, v -> v * 1.005).limit(60).toList();
            IndicatorMath.MacdSeries macd = IndicatorMath.macd(closes, 12, 26, 9);
            assertThat(macd.dif().size()).isEqualTo(60);
            assertThat(macd.dea().size()).isEqualTo(60);
            assertThat(macd.hist().size()).isEqualTo(60);
            // 上涨趋势中 DIF 应为正
            assertThat(macd.dif().get(59)).isNotNull().isPositive();
        }
    }

    @Nested
    @DisplayName("KDJ")
    class KdjTests {
        @Test
        @DisplayName("前 period-1 个值为 null，之后 K/D/J 有值且 J = 3K - 2D")
        void kdjRecursion() {
            List<StockDaily> records = TestDataBuilder.strongStock();
            IndicatorMath.KdjSeries kdj = IndicatorMath.kdj(records, 9, 3, 3);
            assertThat(kdj.k().get(0)).isNull();
            assertThat(kdj.k().get(8)).isNotNull();
            // J = 3K - 2D
            Double k = kdj.k().get(179);
            Double d = kdj.d().get(179);
            Double j = kdj.j().get(179);
            assertThat(j).isCloseTo(3 * k - 2 * d, within(1e-6));
        }
    }

    @Nested
    @DisplayName("RSI")
    class RsiTests {
        @Test
        @DisplayName("持续上涨 RSI 接近 100")
        void rsiUptrend() {
            List<Double> values = Stream.iterate(10.0, v -> v + 1.0).limit(20).toList();
            Double rsi = IndicatorMath.rsi(values, 14);
            assertThat(rsi).isCloseTo(100.0, within(1e-4));
        }

        @Test
        @DisplayName("持续下跌 RSI 接近 0")
        void rsiDowntrend() {
            List<Double> values = Stream.iterate(30.0, v -> v - 1.0).limit(20).toList();
            Double rsi = IndicatorMath.rsi(values, 14);
            assertThat(rsi).isCloseTo(0.0, within(1e-4));
        }

        @Test
        @DisplayName("数据不足返回 null")
        void rsiInsufficient() {
            assertThat(IndicatorMath.rsi(List.of(1.0, 2.0, 3.0), 14)).isNull();
        }
    }

    @Nested
    @DisplayName("交叉信号 crossSignal")
    class CrossSignalTests {
        @Test
        @DisplayName("金叉：前左 <= 前右 且 当前左 > 当前右")
        void goldenCross() {
            String signal = IndicatorMath.crossSignal(5.0, 6.0, 7.0, 6.5);
            assertThat(signal).isEqualTo("golden_cross");
        }

        @Test
        @DisplayName("死叉：前左 >= 前右 且 当前左 < 当前右")
        void deathCross() {
            String signal = IndicatorMath.crossSignal(7.0, 6.0, 5.0, 6.5);
            assertThat(signal).isEqualTo("death_cross");
        }

        @Test
        @DisplayName("无交叉返回 none")
        void noCross() {
            assertThat(IndicatorMath.crossSignal(5.0, 6.0, 5.5, 6.5)).isEqualTo("none");
        }

        @Test
        @DisplayName("任一为 null 返回 any")
        void nullReturnsAny() {
            assertThat(IndicatorMath.crossSignal(null, 6.0, 7.0, 6.5)).isEqualTo("any");
        }
    }

    @Nested
    @DisplayName("BOLL 状态 bollStatus")
    class BollStatusTests {
        @Test
        @DisplayName("收盘价高于上轨 → above_upper")
        void aboveUpper() {
            IndicatorMath.BollStatus status = IndicatorMath.bollStatus(12.0, 11.0, 10.0, 9.0);
            assertThat(status.position()).isEqualTo("above_upper");
            assertThat(status.width()).isCloseTo((11.0 - 9.0) / 10.0 * 100, within(1e-4));
            assertThat(status.percentB()).isCloseTo((12.0 - 9.0) / (11.0 - 9.0) * 100, within(1e-4));
        }

        @Test
        @DisplayName("收盘价在中轨和上轨之间上半 → upper_zone")
        void upperZone() {
            double mid = 10.0, upper = 11.0;
            double price = (upper + mid) / 2; // 边界值
            IndicatorMath.BollStatus status = IndicatorMath.bollStatus(price, upper, mid, 9.0);
            assertThat(status.position()).isEqualTo("upper_zone");
        }

        @Test
        @DisplayName("upper == lower 时返回 middle_upper, width=0, %B=50")
        void degenerateBand() {
            IndicatorMath.BollStatus status = IndicatorMath.bollStatus(10.0, 10.0, 10.0, 10.0);
            assertThat(status.position()).isEqualTo("middle_upper");
            assertThat(status.width()).isCloseTo(0.0, within(1e-10));
            assertThat(status.percentB()).isCloseTo(50.0, within(1e-10));
        }

        @Test
        @DisplayName("任一为 null 返回 any")
        void nullReturnsAny() {
            IndicatorMath.BollStatus status = IndicatorMath.bollStatus(10.0, null, 10.0, 9.0);
            assertThat(status.position()).isEqualTo("any");
            assertThat(status.width()).isNull();
        }
    }

    @Nested
    @DisplayName("综合评分 scoreCandidate")
    class ScoreTests {
        @Test
        @DisplayName("评分公式与 Python round(..., 4) 一致")
        void scoreFormula() {
            double score = IndicatorMath.scoreCandidate(
                    1.5,  // pctChange
                    10.0, 50.0, 100.0,  // return20/60/120
                    1.5,  // volumeRatio
                    3.0,  // amplitude
                    0.05, // macdHist
                    75.0  // bollPercentB
            );
            double expected = round(
                    10.0 * 0.30 + 50.0 * 0.25 + 100.0 * 0.15
                            + 1.5 * 0.10
                            + Math.max(1.5 - 1.0, 0.0) * 10
                            + 0.05 * 4
                            + 75.0 * 0.08
                            - 3.0 * 0.05,
                    4
            );
            assertThat(score).isCloseTo(expected, within(1e-4));
        }

        @Test
        @DisplayName("null 值按 0 或默认值处理")
        void scoreWithNulls() {
            double score = IndicatorMath.scoreCandidate(1.0, null, null, null, null, 2.0, null, null);
            double expected = round(
                    0 * 0.30 + 0 * 0.25 + 0 * 0.15
                            + 1.0 * 0.10
                            + Math.max(1.0 - 1.0, 0.0) * 10
                            + 0 * 4
                            + 50.0 * 0.08
                            - 2.0 * 0.05,
                    4
            );
            assertThat(score).isCloseTo(expected, within(1e-4));
        }
    }

    // --- 辅助方法 ---
    private static double mean(List<Double> values) {
        return values.stream().mapToDouble(Double::doubleValue).average().orElse(0);
    }

    private static double round(double value, int scale) {
        double factor = Math.pow(10, scale);
        return Math.round(value * factor) / factor;
    }
}
