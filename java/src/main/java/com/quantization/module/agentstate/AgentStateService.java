package com.quantization.module.agentstate;

import com.quantization.module.agentstate.dto.AgentStateDto;
import com.quantization.module.agentstate.dto.AgentStateRequest;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Optional;

/**
 * Agent 狀態服務 — 提供狀態持久化和恢復。
 * 單行模式（state_key='default'），upsert 語義。
 */
@Service
public class AgentStateService {

    private static final String DEFAULT_KEY = "default";

    private final AgentStateRepository repository;

    public AgentStateService(AgentStateRepository repository) {
        this.repository = repository;
    }

    /** 保存或更新 Agent 狀態（upsert） */
    public AgentStateDto save(AgentStateRequest request) {
        String key = request.stateKey() != null ? request.stateKey() : DEFAULT_KEY;
        Optional<AgentStateEntity> existing = repository.findByStateKey(key);
        AgentStateEntity entity;
        if (existing.isPresent()) {
            entity = existing.get();
            entity.setStateJson(request.stateJson());
            entity.setCurrentIteration(request.currentIteration() != null ? request.currentIteration() : 0);
            entity.setBestScore(request.bestScore() != null ? request.bestScore() : -999);
            entity.setRetrospectiveCount(request.retrospectiveCount() != null ? request.retrospectiveCount() : 0);
            entity.setUpdatedAt(LocalDateTime.now());
        } else {
            entity = new AgentStateEntity();
            entity.setStateKey(key);
            entity.setStateJson(request.stateJson());
            entity.setCurrentIteration(request.currentIteration() != null ? request.currentIteration() : 0);
            entity.setBestScore(request.bestScore() != null ? request.bestScore() : -999);
            entity.setRetrospectiveCount(request.retrospectiveCount() != null ? request.retrospectiveCount() : 0);
            entity.setUpdatedAt(LocalDateTime.now());
            entity.setCreatedAt(LocalDateTime.now());
        }
        entity = repository.save(entity);
        return toDto(entity);
    }

    /** 讀取 Agent 狀態（單行模式） */
    public AgentStateDto load(String stateKey) {
        String key = stateKey != null ? stateKey : DEFAULT_KEY;
        return repository.findByStateKey(key).map(this::toDto).orElse(null);
    }

    /** 讀取默認狀態 */
    public AgentStateDto loadDefault() {
        return load(DEFAULT_KEY);
    }

    private AgentStateDto toDto(AgentStateEntity e) {
        return new AgentStateDto(
                e.getId(), e.getStateKey(), e.getStateJson(),
                e.getCurrentIteration(), e.getBestScore(), e.getRetrospectiveCount(),
                e.getUpdatedAt(), e.getCreatedAt()
        );
    }
}
