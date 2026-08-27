package com.quantization.module.indicator;

import com.quantization.module.stock.StockDaily;

import java.util.List;

/**
 * 指标计算器接口 — 注册表模式的核心抽象。
 * <p>
 * 每个实现类负责一种（或一组）技术指标的计算，通过 {@link #name()} 标识自身，
 * 通过 {@link #calculate(IndicatorSnapshotBuilder, List, int)} 将结果写入可变的
 * {@link IndicatorSnapshotBuilder}。新增指标只需实现本接口并加 {@code @Component}，
 * 无需修改 {@link IndicatorEngine}。
 * <p>
 * 注意：{@link IndicatorSnapshot} 为不可变 record，故计算器写入的是可变构建器，
 * 由 {@link IndicatorEngine#buildSnapshot} 在所有计算器执行完毕后统一构建快照。
 *
 * @param history  原始行情序列（按时间升序）
 * @param index    待计算的目标索引（通常为最新交易日 {@code history.size()-1}）
 */
public interface IndicatorCalculator {

    /** 指标名称，作为注册表 key（如 "MA"、"RSI"、"KDJ"）。 */
    String name();

    /**
     * 计算指标并写入构建器。
     *
     * @param builder 指标快照构建器（含基础字段、closes 序列与配置）
     * @param history 原始行情序列
     * @param index   目标索引
     */
    void calculate(IndicatorSnapshotBuilder builder, List<StockDaily> history, int index);
}
