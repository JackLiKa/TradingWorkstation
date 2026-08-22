package com.quantization.common.exception;

import com.quantization.common.api.ApiResponse;
import com.quantization.common.api.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

/**
 * 全局异常处理器，统一拦截 Controller 层抛出的异常并转换为标准 {@link ApiResponse}。
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 处理业务异常，根据错误码映射对应的 HTTP 状态码。
     *
     * @param ex 业务异常
     * @return 包含错误信息的响应实体
     */
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusiness(BusinessException ex) {
        log.warn("业务异常: code={}, message={}", ex.getCode(), ex.getMessage());
        HttpStatus status = switch (ex.getCode()) {
            case NOT_FOUND -> HttpStatus.NOT_FOUND;
            case BAD_REQUEST, VALIDATION_ERROR -> HttpStatus.BAD_REQUEST;
            default -> HttpStatus.INTERNAL_SERVER_ERROR;
        };
        return ResponseEntity.status(status).body(ApiResponse.fail(ex.getCode(), ex.getMessage()));
    }

    /**
     * 处理参数校验异常，聚合所有字段错误信息。
     *
     * @param ex 参数校验异常
     * @return 包含校验错误详情的 400 响应
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidation(MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getFieldErrors().stream()
                .map(this::formatFieldError)
                .collect(Collectors.joining("; "));
        return ResponseEntity.badRequest()
                .body(ApiResponse.fail(ErrorCode.VALIDATION_ERROR, message));
    }

    /**
     * 处理未捕获的未知异常，返回 500 状态码。
     *
     * @param ex 未知异常
     * @return 包含错误信息的 500 响应
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleUnexpected(Exception ex) {
        log.error("未处理异常", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.fail(ErrorCode.INTERNAL_ERROR, "服务器内部错误：" + ex.getMessage()));
    }

    /**
     * 格式化字段校验错误为 "字段名: 错误消息" 形式。
     *
     * @param error 字段校验错误
     * @return 格式化后的错误描述
     */
    private String formatFieldError(FieldError error) {
        return error.getField() + ": " + error.getDefaultMessage();
    }
}
