package com.quantization.module.log.dto;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 統一日誌條目 DTO — 用於日誌頁面 API 返回，聚合所有日誌來源。
 *
 * 來源分類：
 * - system: HTTP 請求日誌（方法/路徑/狀態碼/IP/耗時）
 * - java:   Java 後端應用日誌（logback 輸出）
 * - agent:  Agent 服務日誌（agent.log 文件）
 * - ai:     AI 調用日誌（ai_call_log 表，優化各階段）
 */
public record LogEntry(
        String id,               // 唯一標識（source + ":" + timestamp + ":" + seq）
        String source,           // system | java | agent | ai
        String level,            // INFO | WARN | ERROR | DEBUG
        String message,          // 摘要消息
        LocalDateTime timestamp, // 時間戳
        Map<String, Object> details  // 詳細信息（展開查看）
) {}
