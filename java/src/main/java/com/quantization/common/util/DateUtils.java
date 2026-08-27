package com.quantization.common.util;

import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;

/**
 * 日期工具类，提供 ISO 格式（yyyy-MM-dd）的日期解析与格式化。
 */
@Component
public final class DateUtils {
    private static final DateTimeFormatter ISO = DateTimeFormatter.ISO_LOCAL_DATE;

    private DateUtils() {}

    /**
     * 将 ISO 格式字符串解析为 {@link LocalDate}，解析失败返回 null。
     *
     * @param text 日期字符串（yyyy-MM-dd），可为 null 或空白
     * @return 解析后的 LocalDate，或 null
     */
    public static LocalDate parse(String text) {
        if (text == null || text.isBlank()) return null;
        try {
            return LocalDate.parse(text.trim(), ISO);
        } catch (DateTimeParseException e) {
            return null;
        }
    }

    /**
     * 将 {@link LocalDate} 格式化为 ISO 字符串（yyyy-MM-dd），null 返回 null。
     *
     * @param date 待格式化的日期，可为 null
     * @return ISO 格式字符串，或 null
     */
    public static String format(LocalDate date) {
        return date == null ? null : date.format(ISO);
    }
}
