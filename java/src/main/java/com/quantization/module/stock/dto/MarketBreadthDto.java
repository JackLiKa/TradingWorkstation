package com.quantization.module.stock.dto;

import java.util.Map;

/**
 * 市場廣度 DTO — 描述大盤/風格/行業的整體強弱與一致性。
 *
 * @param days              分析天數
 * @param compositeBreadth  綜合指數廣度（上證/深證綜指等）
 * @param scaleBreadth      規模指數廣度（大盤/中盤/小盤/創業板等）
 * @param styleBreadth      風格指數廣度（成長/價值）
 * @param leadingCategories 領漲分類（按 category_code 分組的累計漲幅）
 * @param laggingCategories 滯漲分類
 * @param summary           人工可讀摘要
 */
public record MarketBreadthDto(
        int days,
        Map<String, Double> compositeBreadth,
        Map<String, Double> scaleBreadth,
        Map<String, Double> styleBreadth,
        Map<String, Double> leadingCategories,
        Map<String, Double> laggingCategories,
        String summary
) {
}
