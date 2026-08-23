package com.quantization.module.chat.dto;

import java.time.LocalDateTime;

/**
 * 聊天消息 DTO — 用于 API 返回。
 */
public record ChatMessageDto(
        Long id,
        Long conversationId,
        String role,
        String content,
        String provider,
        String modelName,
        String citationsJson,
        String toolCallsJson,
        Integer tokensUsed,
        LocalDateTime createdAt
) {}
