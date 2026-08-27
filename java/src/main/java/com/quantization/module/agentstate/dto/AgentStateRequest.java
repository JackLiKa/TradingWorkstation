package com.quantization.module.agentstate.dto;

/**
 * Agent 狀態持久化請求體 — Agent 服務提交完整狀態 JSON。
 */
public record AgentStateRequest(
        String stateKey,
        String stateJson,
        Integer currentIteration,
        Double bestScore,
        Integer retrospectiveCount
) {}
