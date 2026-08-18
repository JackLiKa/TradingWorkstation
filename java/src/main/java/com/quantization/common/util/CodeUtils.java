package com.quantization.common.util;

import org.springframework.stereotype.Component;

import java.util.Locale;

/**
 * 股票代码工具类，提供 baostock 代码格式判断与规范化。
 * <p>
 * 与原 Python {@code _build_code_filter} 语义对齐，支持完整代码（sh.600000）、
 * 6 位数字代码、市场前缀（sh/sz）等多种格式的识别。
 * </p>
 */
@Component
public final class CodeUtils {
    private CodeUtils() {}

    /**
     * 与原 Python _build_code_filter 语义对齐：判断是否为完整 baostock 代码（含点且长度>=9）。
     *
     * @param code 待判断的代码字符串
     * @return true 表示为完整代码（如 "sh.600000"）
     */
    public static boolean isFullCode(String code) {
        if (code == null) return false;
        String normalized = code.trim();
        return normalized.contains(".") && normalized.length() >= 9;
    }

    /**
     * 规范化代码：去除首尾空白，null 返回空字符串。
     *
     * @param code 原始代码
     * @return 规范化后的代码
     */
    public static String normalize(String code) {
        return code == null ? "" : code.trim();
    }

    /**
     * 6 位数字代码 → 转 %.NNNNNN 模糊匹配
     *
     * @param code 待判断的代码
     * @return true 表示为纯 6 位数字代码
     */
    public static boolean isPureSixDigit(String code) {
        String n = normalize(code);
        return n.length() == 6 && n.chars().allMatch(Character::isDigit);
    }

    /**
     * 判断代码是否以市场前缀（sh 或 sz）开头。
     *
     * @param code 待判断的代码
     * @return true 表示以 sh. 或 sz. 开头
     */
    public static boolean startsWithMarket(String code) {
        String n = normalize(code).toLowerCase(Locale.ROOT);
        return n.startsWith("sh") || n.startsWith("sz");
    }
}
