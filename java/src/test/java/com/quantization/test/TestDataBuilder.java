package com.quantization.test;

import com.quantization.module.stock.StockDaily;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;

/**
 * 测试数据构建器（忠实移植 Python tests/test_dashboard_service.py 中的 _build_symbol_records）。
 * 生成 180 天的合成行情，用于指标计算、选股、回测的单元测试。
 */
public final class TestDataBuilder {

    private TestDataBuilder() {}

    /**
     * 构建一只股票 180 天的行情数据，与 Python _build_symbol_records 完全对齐。
     *
     * @param code         股票代码
     * @param startDate    起始日期
     * @param basePrice    基准价格
     * @param dailyGrowth  日均增长率
     * @param volumeBase   成交量基数
     * @param isSt         是否 ST (0 或 1)
     */
    public static List<StockDaily> buildSymbolRecords(
            String code, LocalDate startDate, double basePrice,
            double dailyGrowth, long volumeBase, int isSt) {
        double price = basePrice;
        List<StockDaily> records = new ArrayList<>(180);
        for (int offset = 0; offset < 180; offset++) {
            LocalDate tradeDate = startDate.plus(offset, ChronoUnit.DAYS);
            double growth = dailyGrowth + ((offset % 5) - 2) * 0.0015;
            double closePrice = round(price * (1 + growth), 4);
            double openPrice = round(price * (1 - 0.004), 4);
            double highPrice = round(Math.max(price, closePrice) * 1.012, 4);
            double lowPrice = round(Math.min(price, closePrice) * 0.988, 4);
            double pctChange = round((closePrice / price - 1) * 100, 4);
            long volume = volumeBase + offset * 6_000L;
            double amount = round(closePrice * volume, 2);
            double turn = round(1.0 + offset * 0.025, 4);
            records.add(new StockDaily(
                    code, tradeDate,
                    openPrice, highPrice, lowPrice, closePrice, round(price, 4),
                    volume, amount, 3,
                    turn, 1, pctChange, isSt
            ));
            price = closePrice;
        }
        return records;
    }

    /** 强势股：sh.600000，日均增长 1.1%，与 Python 测试一致。 */
    public static List<StockDaily> strongStock() {
        return buildSymbolRecords("sh.600000", LocalDate.of(2026, 1, 2), 10.0, 0.011, 1_200_000L, 0);
    }

    /** 中等股：sz.000001，日均增长 0.3%。 */
    public static List<StockDaily> mediumStock() {
        return buildSymbolRecords("sz.000001", LocalDate.of(2026, 1, 2), 8.0, 0.003, 900_000L, 0);
    }

    /** 弱势股：sh.600010，日均增长 -0.15%。 */
    public static List<StockDaily> weakStock() {
        return buildSymbolRecords("sh.600010", LocalDate.of(2026, 1, 2), 7.5, -0.0015, 750_000L, 0);
    }

    /** ST 股：sz.000777，日均增长 0.9%，isSt=1。 */
    public static List<StockDaily> stStock() {
        return buildSymbolRecords("sz.000777", LocalDate.of(2026, 1, 2), 6.0, 0.009, 600_000L, 1);
    }

    /** 全部 4 只股票的行情合并（与 Python FakeStockRepository._records 一致）。 */
    public static List<StockDaily> allRecords() {
        List<StockDaily> all = new ArrayList<>();
        all.addAll(strongStock());
        all.addAll(mediumStock());
        all.addAll(weakStock());
        all.addAll(stStock());
        return all;
    }

    /** 2026-06-20 对应的 offset（从 2026-01-02 起第 169 天，索引 169）。 */
    public static final LocalDate SCREEN_DATE = LocalDate.of(2026, 6, 20);

    private static double round(double value, int scale) {
        double factor = Math.pow(10, scale);
        return Math.round(value * factor) / factor;
    }
}
