package com.quantization.module.chat.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 发送聊天消息请求 — 用户发送消息到指定对话。
 */
public record ChatSendRequest(
        @NotBlank(message = "content 不能为空")
        @Size(max = 10000, message = "content 长度不能超过 10000") String content,

        String provider
) {}
