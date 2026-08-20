package com.quantization.module.stock.dto;

import java.util.List;
import java.util.Map;

/**
 * 輪動信號 DTO — 描述行業與風格輪動方向。
 *
 * @param days               分析天數
 * @param industryRotation   一級/二級行業輪動強度（category_code -> {name: change%}）
 * @param styleRotation      成長 vs 價值、大盤 vs 小盤的相對強度
 * @param leadingIndustries  領漲行業列表（按累計漲幅排序）
 * @param laggingIndustries  滯漲行業列表
 * @param rotationStrength   輪動強度分數（0-100，越高表示輪動越明顯）
 * @param summary            人工可讀摘要
 */
public record RotationSignalDto(
        int days,
        Map<String, Map<String, Double>> industryRotation,
        Map<String, Double> styleRotation,
        List<RankEntryDto> leadingIndustries,
        List<RankEntryDto> laggingIndustries,
        double rotationStrength,
        String summary
) {
    /**
     * 排名項 DTO（用於領漲/滯漲列表）。
     */
    public record RankEntryDto(String name, double change) {
    }
}
