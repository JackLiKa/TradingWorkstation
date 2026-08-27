package com.quantization.module.stock.dto;

import com.quantization.module.stock.IndexMetadataEntity;

/**
 * 指數元數據 DTO — 代碼/名稱/分類。
 */
public record IndexMetadataDto(
        String code,
        String name,
        String category,
        String categoryCode
) {
    public static IndexMetadataDto from(IndexMetadataEntity e) {
        return new IndexMetadataDto(e.getCode(), e.getName(), e.getCategory(), e.getCategoryCode());
    }
}
