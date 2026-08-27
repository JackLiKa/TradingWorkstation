package com.quantization.module.chat.dto;

/**
 * 保存 AI 回复请求 — Agent 服务流式完成后提交完整回复。
 */
public record ChatSaveReplyRequest(
        String content,
        String provider,
        String modelName,
        String citationsJson,
        String toolCallsJson,
        Integer tokensUsed
) {}
