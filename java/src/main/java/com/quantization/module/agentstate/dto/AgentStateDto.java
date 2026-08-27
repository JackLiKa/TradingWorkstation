package com.quantization.module.agentstate.dto;

import java.time.LocalDateTime;

/**
 * Agent 狀態 DTO — 用於 API 返回。
 */
public record AgentStateDto(
        Long id,
        String stateKey,
        String stateJson,
        Integer currentIteration,
        Double bestScore,
        Integer retrospectiveCount,
        LocalDateTime updatedAt,
        LocalDateTime createdAt
) {}
