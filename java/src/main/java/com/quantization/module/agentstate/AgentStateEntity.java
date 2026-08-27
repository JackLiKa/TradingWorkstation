package com.quantization.module.agentstate;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * Agent 狀態持久化實體 — 跨重啟恢復優化循環狀態。
 * 單行模式（state_key='default'），Agent 啟動時讀取，每輪結束後寫入。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "agent_state")
public class AgentStateEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** 狀態鍵（單行模式，固定為 'default'） */
    @Column(name = "state_key", nullable = false, length = 64, unique = true)
    private String stateKey;

    /** 完整狀態 JSON（含 best_criteria/config、current_reflection、retrospective 等） */
    @Column(name = "state_json", columnDefinition = "LONGTEXT", nullable = false)
    private String stateJson;

    /** 當前迭代輪次（冗餘字段，便於查詢） */
    @Column(name = "current_iteration", nullable = false)
    private Integer currentIteration;

    /** 歷史最高評分（冗餘字段，便於查詢） */
    @Column(name = "best_score", nullable = false)
    private Double bestScore;

    /** 回顧分析次數（冗餘字段，便於查詢） */
    @Column(name = "retrospective_count", nullable = false)
    private Integer retrospectiveCount;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
