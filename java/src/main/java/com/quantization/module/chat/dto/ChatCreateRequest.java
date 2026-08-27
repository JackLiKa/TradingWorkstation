package com.quantization.module.chat.dto;

/**
 * 创建对话请求。
 */
public record ChatCreateRequest(
        String title,
        String provider
) {}
