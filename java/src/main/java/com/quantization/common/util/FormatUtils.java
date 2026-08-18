package com.quantization.common.util;

import org.springframework.stereotype.Component;

import java.util.Locale;

/**
 * 格式化工具类，提供百分比、金额和成交量的中文友好格式化。
 */
@Component
public final class FormatUtils {
    private FormatUtils() {}

    /**
     * 格式化为百分比字符串（保留两位小数，如 "12.34%"）。
     *
     * @param value 百分比值，可为 null
     * @return 格式化后的百分比字符串
     */
    public static String formatPercent(Double value) {
        if (value == null) return "0.00%";
        return String.format(Locale.US, "%.2f%%", value);
    }

    /**
     * 格式化金额：超过 1 亿显示"亿"，超过 1 万显示"万"，否则显示原始值。
     *
     * @param value 金额值，可为 null
     * @return 格式化后的金额字符串
     */
    public static String formatCurrency(Double value) {
        if (value == null) return "0";
        if (value >= 100_000_000) return String.format(Locale.US, "%.2f 亿", value / 100_000_000);
        if (value >= 10_000) return String.format(Locale.US, "%.2f 万", value / 10_000);
        return String.format(Locale.US, "%,.2f", value);
    }

    /**
     * 格式化成交量：超过 1 亿显示"亿"，超过 1 万显示"万"，否则显示原始值。
     *
     * @param volume 成交量，可为 null
     * @return 格式化后的成交量字符串
     */
    public static String formatVolume(Long volume) {
        if (volume == null) return "-";
        if (volume >= 100_000_000L) return String.format(Locale.US, "%.2f亿", volume / 100_000_000.0);
        if (volume >= 10_000) return String.format(Locale.US, "%.2f万", volume / 10_000.0);
        return String.valueOf(volume);
    }
}
