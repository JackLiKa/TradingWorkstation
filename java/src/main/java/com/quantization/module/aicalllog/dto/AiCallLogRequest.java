package com.quantization.module.aicalllog.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

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
        @Min(value = 1, message = "iteration 必須 >= 1") Integer iteration,
        @NotBlank(message = "stageName 不能為空")
        @Size(max = 64, message = "stageName 長度不能超過 64")
        @Pattern(regexp = "market_news|industry_analysis|market_analysis|strategy_generation|backtest_reflection|prompt_generation|judge|unknown",
                 message = "stageName 必須為合法的階段標識") String stageName,
        @Size(max = 128, message = "stageDisplayName 長度不能超過 128") String stageDisplayName,
        @NotBlank(message = "provider 不能為空")
        @Size(max = 32, message = "provider 長度不能超過 32")
        @Pattern(regexp = "qoder|devin|none", message = "provider 必須為 qoder/devin/none") String provider,
        @Size(max = 64, message = "modelName 長度不能超過 64") String modelName,
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
