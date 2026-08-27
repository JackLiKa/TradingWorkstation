package com.quantization.module.aicalllog.dto;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * AI 調用日誌 DTO — 用於 API 返回和 Agent 服務提交。
 */
public record AiCallLogDto(
        Long id,
        Integer iteration,
        String stageName,
        String stageDisplayName,
        String provider,
        String modelName,
        String inputJson,
        String outputText,
        String outputJson,
        Double judgeScore,
        Boolean judgePassed,
        String judgeFeedback,
        Integer attempts,
        Integer durationMs,
        String error,
        LocalDateTime createdAt
) {}
