package com.quantization.common.exception;

import lombok.Getter;

/**
 * 业务异常，携带错误码供 {@link GlobalExceptionHandler} 映射 HTTP 状态码。
 */
@Getter
public class BusinessException extends RuntimeException {
    /** 错误码（参见 {@link com.quantization.common.api.ErrorCode}） */
    private final String code;

    /**
     * 构建业务异常。
     *
     * @param code    错误码
     * @param message 异常消息
     */
    public BusinessException(String code, String message) {
        super(message);
        this.code = code;
    }

    /**
     * 构建业务异常（含根因）。
     *
     * @param code    错误码
     * @param message 异常消息
     * @param cause   根因异常
     */
    public BusinessException(String code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }
}
