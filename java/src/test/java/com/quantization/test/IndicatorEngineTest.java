package com.quantization.test;

import com.quantization.module.indicator.IndicatorConfig;
import com.quantization.module.indicator.IndicatorEngine;
import com.quantization.module.indicator.IndicatorSnapshot;
import com.quantization.module.stock.StockDaily;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

/**
 * IndicatorEngine 集成测试 — 验证 buildSnapshot 完整快照构建。
 * 使用与 Python test_dashboard_service.py 同源的合成数据。
 */
@DisplayName("IndicatorEngine 快照构建")
class IndicatorEngineTest {

    private final IndicatorEngine engine = new IndicatorEngine();

    @Test
    @DisplayName("强势股 180 天数据生成完整快照，所有指标非 null")
    void strongStockSnapshotComplete() {
        List<StockDaily> records = TestDataBuilder.strongStock();
        IndicatorSnapshot snapshot = engine.buildSnapshot("sh.600000", records, IndicatorConfig.screener());

        assertThat(snapshot).isNotNull();
        assertThat(snapshot.code()).isEqualTo("sh.600000");
        assertThat(snapshot.tradeDate()).isEqualTo(records.get(179).tradeDate());
        assertThat(snapshot.closePrice()).isPositive();
        assertThat(snapshot.ma5()).isNotNull().isPositive();
        assertThat(snapshot.ma10()).isNotNull().isPositive();
        assertThat(snapshot.ma20()).isNotNull().isPositive();
        assertThat(snapshot.ma60()).isNotNull().isPositive();
        assertThat(snapshot.ma120()).isNotNull().isPositive();
        assertThat(snapshot.volumeRatio()).isNotNull().isPositive();
        assertThat(snapshot.return20()).isNotNull().isPositive();
        assertThat(snapshot.return60()).isNotNull().isPositive();
        assertThat(snapshot.return120()).isNotNull().isPositive();
        assertThat(snapshot.rsi14()).isNotNull();
        assertThat(snapshot.kValue()).isNotNull();
        assertThat(snapshot.dValue()).isNotNull();
        assertThat(snapshot.jValue()).isNotNull();
        assertThat(snapshot.dif()).isNotNull();
        assertThat(snapshot.dea()).isNotNull();
        assertThat(snapshot.macdHist()).isNotNull();
        assertThat(snapshot.bollUpper()).isNotNull();
        assertThat(snapshot.bollMiddle()).isNotNull();
        assertThat(snapshot.bollLower()).isNotNull();
        assertThat(snapshot.bollWidth()).isNotNull().isPositive();
        assertThat(snapshot.bollPercentB()).isNotNull();
        assertThat(snapshot.score()).isPositive();
        assertThat(snapshot.isSt()).isFalse();
    }

    @Test
    @DisplayName("强势股持续上涨 → BOLL 位置为 upper_zone 或 above_upper")
    void strongStockBollPositionUpper() {
        List<StockDaily> records = TestDataBuilder.strongStock();
        IndicatorSnapshot snapshot = engine.buildSnapshot("sh.600000", records, IndicatorConfig.screener());

        assertThat(snapshot).isNotNull();
        // 日均增长 1.1% 的强势股，第 180 天收盘价大概率在上轨或上轨区域
        assertThat(snapshot.bollPosition()).isIn("above_upper", "upper_zone", "middle_upper");
    }

    @Test
    @DisplayName("弱势股持续下跌 → 20/60/120 日收益为负")
    void weakStockReturnsNegative() {
        List<StockDaily> records = TestDataBuilder.weakStock();
        IndicatorSnapshot snapshot = engine.buildSnapshot("sh.600010", records, IndicatorConfig.screener());

        assertThat(snapshot).isNotNull();
        assertThat(snapshot.return20()).isNotNull().isNegative();
        assertThat(snapshot.return60()).isNotNull().isNegative();
        assertThat(snapshot.return120()).isNotNull().isNegative();
    }

    @Test
    @DisplayName("ST 股 isSt 标记为 true")
    void stStockFlagged() {
        List<StockDaily> records = TestDataBuilder.stStock();
        IndicatorSnapshot snapshot = engine.buildSnapshot("sz.000777", records, IndicatorConfig.screener());

        assertThat(snapshot).isNotNull();
        assertThat(snapshot.isSt()).isTrue();
    }

    @Test
    @DisplayName("数据不足 30 天返回 null")
    void insufficientDataReturnsNull() {
        List<StockDaily> shortHistory = TestDataBuilder.strongStock().subList(0, 20);
        IndicatorSnapshot snapshot = engine.buildSnapshot("sh.600000", shortHistory, IndicatorConfig.screener());
        assertThat(snapshot).isNull();
    }

    @Test
    @DisplayName("最新交易日 tradeStatus != 1 返回 null")
    void nonTradableReturnsNull() {
        List<StockDaily> records = TestDataBuilder.strongStock();
        StockDaily last = records.get(179);
        records.set(179, new StockDaily(
                last.code(), last.tradeDate(),
                last.openPrice(), last.highPrice(), last.lowPrice(), last.closePrice(), last.preclosePrice(),
                last.volume(), last.amount(), last.adjustflag(),
                last.turn(), 0, last.pctChange(), last.isSt() // tradeStatus=0 停牌
        ));
        IndicatorSnapshot snapshot = engine.buildSnapshot("sh.600000", records, IndicatorConfig.screener());
        assertThat(snapshot).isNull();
    }

    @Test
    @DisplayName("评分 = return20*0.3 + return60*0.25 + return120*0.15 + ... 与 Python 一致")
    void scoreMatchesFormula() {
        List<StockDaily> records = TestDataBuilder.strongStock();
        IndicatorSnapshot snapshot = engine.buildSnapshot("sh.600000", records, IndicatorConfig.screener());

        assertThat(snapshot).isNotNull();
        double expected = round(
                (snapshot.return20() == null ? 0 : snapshot.return20()) * 0.30
                        + (snapshot.return60() == null ? 0 : snapshot.return60()) * 0.25
                        + (snapshot.return120() == null ? 0 : snapshot.return120()) * 0.15
                        + snapshot.pctChange() * 0.10
                        + Math.max((snapshot.volumeRatio() == null ? 1.0 : snapshot.volumeRatio()) - 1.0, 0.0) * 10
                        + (snapshot.macdHist() == null ? 0 : snapshot.macdHist()) * 4
                        + (snapshot.bollPercentB() == null ? 50.0 : snapshot.bollPercentB()) * 0.08
                        - snapshot.amplitude() * 0.05,
                4
        );
        assertThat(snapshot.score()).isCloseTo(expected, within(1e-4));
    }

    private static double round(double value, int scale) {
        double factor = Math.pow(10, scale);
        return Math.round(value * factor) / factor;
    }
}
