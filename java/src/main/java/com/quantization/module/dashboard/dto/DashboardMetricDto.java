package com.quantization.module.dashboard.dto;

/**
 * 仪表盘指标卡片 DTO，包含标题、值和副标题。
 *
 * @param title    指标标题
 * @param value    指标值（格式化后的字符串）
 * @param subtitle 副标题说明
 */
public record DashboardMetricDto(String title, String value, String subtitle) {
}
