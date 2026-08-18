package com.quantization.common.util;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

/**
 * 数值计算工具类，提供四舍五入、均值和标准差等基础运算。
 * 与原 Python statistics 模块语义对齐。
 */
public final class DecimalUtils {
    private DecimalUtils() {}

    /**
     * 四舍五入到指定小数位。
     *
     * @param value 原始值，可为 null
     * @param scale 保留小数位数
     * @return 四舍五入后的 Double，或 null
     */
    public static Double round(Double value, int scale) {
        if (value == null) return null;
        return BigDecimal.valueOf(value).setScale(scale, RoundingMode.HALF_UP).doubleValue();
    }

    /**
     * 计算算术平均值。
     *
     * @param values 数值列表，可为 null 或空
     * @return 平均值，或 null（列表为空时）
     */
    public static Double mean(List<Double> values) {
        if (values == null || values.isEmpty()) return null;
        double sum = 0.0;
        for (Double v : values) sum += v;
        return sum / values.size();
    }

    /** 总体标准差（与 Python statistics.pstdev 对齐，分母为 n） */
    public static Double pstdev(List<Double> values) {
        if (values == null || values.size() < 2) return 0.0;
        double m = mean(values);
        double sum = 0.0;
        for (Double v : values) {
            double d = v - m;
            sum += d * d;
        }
        return Math.sqrt(sum / values.size());
    }
}
