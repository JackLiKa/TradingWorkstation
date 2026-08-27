package com.quantization.common.api;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * 统一 API 响应封装，所有 Controller 返回值均使用此格式。
 * <p>
 * 包含 success 标志、错误码、消息和业务数据，序列化时自动忽略 null 字段。
 * </p>
 *
 * @param <T> 业务数据类型
 */
@Getter
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ApiResponse<T> {
    /** 请求是否成功 */
    private final boolean success;
    /** 错误码（成功时为 "OK"） */
    private final String code;
    /** 提示消息 */
    private final String message;
    /** 业务数据 */
    private final T data;

    /**
     * 构建成功响应（默认消息 "成功"）。
     *
     * @param data 业务数据
     * @param <T>  数据类型
     * @return 成功响应
     */
    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(true, ErrorCode.OK.name(), "成功", data);
    }

    /**
     * 构建成功响应（自定义消息）。
     *
     * @param data    业务数据
     * @param message 自定义提示消息
     * @param <T>     数据类型
     * @return 成功响应
     */
    public static <T> ApiResponse<T> ok(T data, String message) {
        return new ApiResponse<>(true, ErrorCode.OK.name(), message, data);
    }

    /**
     * 构建失败响应。
     *
     * @param code    错误码（参见 {@link ErrorCode}）
     * @param message 错误消息
     * @param <T>     数据类型
     * @return 失败响应（data 为 null）
     */
    public static <T> ApiResponse<T> fail(ErrorCode code, String message) {
        return new ApiResponse<>(false, code.name(), message, null);
    }
}
