package com.quantization.module.stock;

/**
 * 行業景氣度與預測相關的通用數學工具方法（package-private）。
 * 供 {@link com.quantization.module.industry.IndustryService} 和
 * {@link com.quantization.module.forecast.ForecastService} 共用。
 */
public final class StockMathUtils {

    private StockMathUtils() {
    }

    /** 將值標準化到 0-100 區間。 */
    public static double normalize(double value, double min, double max) {
        if (max == min) {
            return 50.0; // 所有值相同時給中間分
        }
        return (value - min) / (max - min) * 100.0;
    }

    public static double min(double[] arr) {
        double m = Double.MAX_VALUE;
        for (double v : arr) {
            if (v < m) m = v;
        }
        return m;
    }

    public static double max(double[] arr) {
        double m = -Double.MAX_VALUE;
        for (double v : arr) {
            if (v > m) m = v;
        }
        return m;
    }

    /** 景氣度等級。 */
    public static String prosperityGrade(double prosperityIndex) {
        if (prosperityIndex >= 80) return "繁榮";
        if (prosperityIndex >= 65) return "景氣";
        if (prosperityIndex >= 50) return "平穩";
        if (prosperityIndex >= 35) return "低迷";
        return "衰退";
    }

    /** 等級數值化（越高越好）。 */
    public static int gradeLevel(String grade) {
        return switch (grade) {
            case "繁榮" -> 5;
            case "景氣" -> 4;
            case "平穩" -> 3;
            case "低迷" -> 2;
            case "衰退" -> 1;
            default -> 0;
        };
    }
}
