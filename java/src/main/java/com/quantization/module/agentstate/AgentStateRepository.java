package com.quantization.module.agentstate;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Agent 狀態 Repository — 單行模式，按 state_key 查詢。
 */
@Repository
public interface AgentStateRepository extends JpaRepository<AgentStateEntity, Long> {

    /** 按 state_key 查詢（單行模式，固定為 'default'） */
    Optional<AgentStateEntity> findByStateKey(String stateKey);
}
