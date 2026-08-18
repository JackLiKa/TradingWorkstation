package com.quantization.module.stock;

import java.time.LocalDate;
import java.util.List;

public interface StockDailyRepositoryCustom {

    boolean ping();

    /** 表总行数、去重代码数、最新交易日、最新交易日(不复权)平均涨跌幅与成交额 */
    StockSummaryProjection summaryMetrics();

    /** 日线表格查询（按 trade_date desc, code 排序，limit） */
    List<StockDailyEntity> searchDaily(StockDailyQuery query);

    /** K 线初始批次（指定 code，按 date desc 取 batchSize 后正序返回） */
    List<StockDailyEntity> candlestick(StockDailyQuery query, int batchSize);

    /** 更早历史（date < beforeDate，按 date desc 取 batchSize 后正序返回） */
    List<StockDailyEntity> olderCandlestick(StockDailyQuery query, LocalDate beforeDate, int batchSize);

    /** 最新交易日 |pctChg| 最大的若干只（不复权口径） */
    List<StockDailyEntity> latestMovers(int limit);

    /** 区间内去重交易日（升序） */
    List<LocalDate> tradeDates(LocalDate start, LocalDate end, int adjustflag);

    /** 区间内全部行情（按 code, date 升序），可限定 codes */
    List<StockDailyEntity> recordsInRange(LocalDate start, LocalDate end, int adjustflag, List<String> codes);

    /** 搜索建議：根據用戶輸入的部分代碼，返回最新交易日匹配的股票列表（含收盤價、漲跌幅） */
    List<StockDailyEntity> suggest(String query, int limit);
}
