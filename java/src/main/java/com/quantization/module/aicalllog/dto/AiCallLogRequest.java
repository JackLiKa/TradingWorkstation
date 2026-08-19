package com.quantization.module.aicalllog.dto;

/**
 * Agent 服務提交 AI 調用日誌的請求體。
 * <p>
 * 標準化 JSON 結構，多重約束：
 * - iteration: 必須 >= 1
 * - stageName: 非空，枚舉值
 * - inputJson: 非空 JSON 字符串，包含 system_prompt + user_prompt + context
 * - outputText: AI 原始輸出
 * - provider: 非空，枚舉 qoder/devin/none
 */
public record AiCallLogRequest(
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
        String error
) {}
