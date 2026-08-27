package com.quantization.module.news.dto;

/**
 * 新闻情感评分同步结果统计。
 */
public record SentimentSyncResultDto(int total, int stored, int duplicated, int failed) {
    public static SentimentSyncResultDto success(int total, int stored, int duplicated, int failed) {
        return new SentimentSyncResultDto(total, stored, duplicated, failed);
    }
}
