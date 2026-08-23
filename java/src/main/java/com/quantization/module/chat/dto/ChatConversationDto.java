package com.quantization.module.chat.dto;

import java.time.LocalDateTime;

/**
 * 聊天对话 DTO — 用于 API 返回。
 */
public record ChatConversationDto(
        Long id,
        String userId,
        String title,
        String provider,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {}
