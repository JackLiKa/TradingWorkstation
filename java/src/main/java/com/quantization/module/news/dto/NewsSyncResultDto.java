package com.quantization.module.news.dto;

import java.util.List;

/**
 * 新闻同步结果 DTO — 返回抓取/存储/去重统计。
 */
public record NewsSyncResultDto(
        String status,
        int fetched,
        int stored,
        int duplicated,
        int failed,
        String message
) {
    public static NewsSyncResultDto success(int fetched, int stored, int duplicated, int failed) {
        return new NewsSyncResultDto("SUCCESS", fetched, stored, duplicated, failed,
                String.format("抓取 %d 条，新存入 %d 条，重复 %d 条，失败 %d 条", fetched, stored, duplicated, failed));
    }

    public static NewsSyncResultDto failed(String message) {
        return new NewsSyncResultDto("FAILED", 0, 0, 0, 0, message);
    }
}
