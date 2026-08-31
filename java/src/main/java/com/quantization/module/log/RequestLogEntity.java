package com.quantization.module.log;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * HTTP 請求日誌實體 — 記錄每個 API 請求的方法、路徑、狀態碼、客戶端 IP、耗時。
 * 用於日誌頁面的「系統請求」分類，支持按 IP/路徑/狀態碼篩選。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "request_log", indexes = {
    @Index(name = "idx_request_log_created", columnList = "created_at"),
    @Index(name = "idx_request_log_path", columnList = "request_path"),
    @Index(name = "idx_request_log_ip", columnList = "client_ip")
})
public class RequestLogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** HTTP 方法：GET/POST/PUT/DELETE */
    @Column(name = "method", nullable = false, length = 10)
    private String method;

    /** 請求路徑（不含 context-path 前綴） */
    @Column(name = "request_path", nullable = false, length = 500)
    private String requestPath;

    /** 查詢參數（可空） */
    @Column(name = "query_string", length = 1000)
    private String queryString;

    /** 響應狀態碼 */
    @Column(name = "status_code")
    private Integer statusCode;

    /** 客戶端 IP */
    @Column(name = "client_ip", length = 64)
    private String clientIp;

    /** 請求耗時（毫秒） */
    @Column(name = "duration_ms")
    private Integer durationMs;

    /** 請求體大小（字節，可空） */
    @Column(name = "content_length")
    private Long contentLength;

    /** User-Agent（截斷） */
    @Column(name = "user_agent", length = 500)
    private String userAgent;

    /** 異常信息（可空） */
    @Column(name = "error", length = 1000)
    private String error;

    /** 創建時間 */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
