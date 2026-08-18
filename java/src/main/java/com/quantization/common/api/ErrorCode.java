package com.quantization.common.api;

import lombok.Getter;

/**
 * 错误码常量定义，用于 {@link ApiResponse} 和 {@link com.quantization.common.exception.BusinessException}。
 */
@Getter
public class ErrorCode {
    public static final String OK = "OK";
    public static final String BAD_REQUEST = "BAD_REQUEST";
    public static final String VALIDATION_ERROR = "VALIDATION_ERROR";
    public static final String NOT_FOUND = "NOT_FOUND";
    public static final String DB_ERROR = "DB_ERROR";
    public static final String SYNC_ERROR = "SYNC_ERROR";
    public static final String INTERNAL_ERROR = "INTERNAL_ERROR";
}
