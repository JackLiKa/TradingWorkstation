package com.quantization.module.dashboard.dto;

import com.quantization.module.chart.dto.CandlestickDto;
import com.quantization.module.stock.dto.HotSymbolDto;
import com.quantization.module.stock.dto.StockDailyDto;
import com.quantization.module.stock.dto.StockDailyQueryDto;

import java.util.List;

/**
 * 仪表盘快照 DTO，聚合指标卡片、行情表格、K线图、波动榜和日志等信息。
 *
 * @param metrics      指标卡片列表
 * @param records      行情表格记录
 * @param chart        K线图数据
 * @param hotSymbols   波动榜
 * @param selectedQuery 当前查询条件
 * @param connected    数据库是否连接正常
 * @param statusText   状态描述文本
 * @param logLines     日志摘要行
 */
public record DashboardSnapshotDto(
        List<DashboardMetricDto> metrics,
        List<StockDailyDto> records,
        CandlestickDto chart,
        List<HotSymbolDto> hotSymbols,
        StockDailyQueryDto selectedQuery,
        boolean connected,
        String statusText,
        List<String> logLines
) {
}
