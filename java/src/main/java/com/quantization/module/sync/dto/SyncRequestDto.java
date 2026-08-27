package com.quantization.module.sync.dto;

import java.time.LocalDate;

/**
 * 数据同步请求。
 *
 * @param adjustflags  復權類型列表，逗號分隔（如 "1,2,3"）；為空時默認 "3"
 * @param startDate    起始日期（incremental 模式可為 null）
 * @param endDate      結束日期（null = 今天）
 * @param codes        指定股票代碼（逗號分隔），為空則用股票清單
 * @param mode         同步模式：incremental=增量更新，range=指定日期範圍
 * @param syncIndex    是否同時同步指數數據
 * @param syncIndustry 是否同時同步行業分類數據
 */
public record SyncRequestDto(
        String adjustflags,
        LocalDate startDate,
        LocalDate endDate,
        String codes,
        String mode,
        Boolean syncIndex,
        Boolean syncIndustry
) {
    /** 向後兼容：單個 adjustflag int 構造。 */
    public SyncRequestDto(int adjustflag, LocalDate startDate, LocalDate endDate, String codes, String mode) {
        this(String.valueOf(adjustflag), startDate, endDate, codes, mode, false, false);
    }

    /** 獲取有效的復權類型字符串（默認 "3"）。 */
    public String effectiveAdjustflags() {
        return (adjustflags == null || adjustflags.isBlank()) ? "3" : adjustflags;
    }

    /** 獲取有效的模式（默認 incremental）。 */
    public String effectiveMode() {
        return (mode == null || mode.isBlank()) ? "incremental" : mode;
    }

    /** 是否同步指數（默認 false）。 */
    public boolean effectiveSyncIndex() {
        return Boolean.TRUE.equals(syncIndex);
    }

    /** 是否同步行業（默認 false）。 */
    public boolean effectiveSyncIndustry() {
        return Boolean.TRUE.equals(syncIndustry);
    }
}
