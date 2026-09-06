package com.quantization.common.api;

import java.util.List;

/**
 * 分批響應包裝類 — 智能分批兜底方案。
 * <p>
 * 當查詢結果超過安全閾值（默認 100 條）時，自動截取前 N 條並附加分批信息。
 * LLM 收到 hasMore=true 時會提示用戶「回復繼續查看更多」，用戶回復「繼續」後
 * LLM 傳入 offset 參數獲取下一批，直到所有數據返回完畢。
 * </p>
 */
public record PaginatedResponse<T>(
        List<T> data,
        boolean hasMore,
        int total,
        int offset,
        int limit,
        String message
) {
    /**
     * 創建分批響應 — 自動截取並生成分批提示。
     *
     * @param allData  完整結果列表
     * @param offset   當前偏移量
     * @param maxLimit 每批最大條數（默認 100）
     * @return 分批響應，包含截取後的數據和分批信息
     */
    public static <T> PaginatedResponse<T> of(List<T> allData, int offset, int maxLimit) {
        if (maxLimit <= 0) maxLimit = 100;
        if (offset < 0) offset = 0;

        int total = allData.size();
        int fromIndex = Math.min(offset, total);
        int toIndex = Math.min(offset + maxLimit, total);
        List<T> pageData = allData.subList(fromIndex, toIndex);
        boolean hasMore = toIndex < total;
        int remaining = total - toIndex;

        String message = hasMore
                ? "還有 " + remaining + " 條數據，回復「繼續」查看更多"
                : null;

        return new PaginatedResponse<>(pageData, hasMore, total, offset, maxLimit, message);
    }

    /**
     * 創建分批響應 — 使用默認每批 100 條。
     */
    public static <T> PaginatedResponse<T> of(List<T> allData, int offset) {
        return of(allData, offset, 100);
    }

    /**
     * 創建分批響應 — 從第一頁開始。
     */
    public static <T> PaginatedResponse<T> of(List<T> allData) {
        return of(allData, 0, 100);
    }
}
