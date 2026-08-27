package com.quantization.common.api;

/**
 * 错误码枚举，用于 {@link ApiResponse} 和 {@link com.quantization.common.exception.BusinessException}。
 * <p>
 * 改为枚举以提供编译期类型安全；序列化时通过 {@link #name()} 保持原有字符串响应格式不变。
 * </p>
 */
public enum ErrorCode {
    OK,
    BAD_REQUEST,
    VALIDATION_ERROR,
    NOT_FOUND,
    DB_ERROR,
    SYNC_ERROR,
    INTERNAL_ERROR
}
