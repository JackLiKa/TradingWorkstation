package com.quantization.module.backtest;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.quantization.common.exception.BusinessException;
import com.quantization.common.api.ErrorCode;
import com.quantization.module.backtest.dto.BacktestConfigDto;
import com.quantization.module.backtest.dto.BacktestResultDto;
import com.quantization.module.backtest.dto.SaveStrategyDto;
import com.quantization.module.backtest.dto.SavedStrategyDetailDto;
import com.quantization.module.backtest.dto.SavedStrategySummaryDto;
import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 回测策略管理服务，负责策略的保存、查询、详情和删除，
 * 选股条件、配置和结果以 JSON 序列化存储。
 */
@Service
@Transactional
public class BacktestStrategyService {

    private final BacktestStrategyRepository repository;
    private final ObjectMapper objectMapper;

    public BacktestStrategyService(BacktestStrategyRepository repository, ObjectMapper objectMapper) {
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    /**
     * 获取全部已保存策略摘要列表（按创建时间倒序）。
     *
     * @return 策略摘要列表
     */
    public List<SavedStrategySummaryDto> list() {
        return repository.findAllByOrderByCreatedAtDesc().stream()
                .map(e -> new SavedStrategySummaryDto(e.getId(), e.getName(), e.getCreatedAt(), e.getUpdatedAt()))
                .toList();
    }

    /**
     * 根据 ID 获取策略详情（含选股条件、配置和可选的回测结果）。
     *
     * @param id 策略 ID
     * @return 策略详情
     * @throws BusinessException 策略不存在时抛出 NOT_FOUND
     */
    public SavedStrategyDetailDto getById(Long id) {
        BacktestStrategyEntity e = repository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND, "策略不存在: " + id));
        return toDetail(e);
    }

    /**
     * 保存回测策略，将选股条件、配置和结果序列化为 JSON 存储。
     *
     * @param dto 策略保存请求
     * @return 已保存的策略详情
     * @throws BusinessException 序列化失败时抛出 INTERNAL_ERROR
     */
    public SavedStrategyDetailDto save(SaveStrategyDto dto) {
        try {
            String criteriaJson = objectMapper.writeValueAsString(dto.criteria());
            String configJson = objectMapper.writeValueAsString(dto.config());
            String resultJson = dto.result() != null ? objectMapper.writeValueAsString(dto.result()) : null;

            BacktestStrategyEntity entity = new BacktestStrategyEntity();
            entity.setName(dto.name());
            entity.setCriteriaJson(criteriaJson);
            entity.setConfigJson(configJson);
            entity.setResultJson(resultJson);
            entity.setCreatedAt(java.time.LocalDateTime.now());
            entity.setUpdatedAt(java.time.LocalDateTime.now());
            entity = repository.save(entity);
            return toDetail(entity);
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.INTERNAL_ERROR, "策略序列化失败: " + e.getMessage(), e);
        }
    }

    /**
     * 根据 ID 删除策略。
     *
     * @param id 策略 ID
     * @throws BusinessException 策略不存在时抛出 NOT_FOUND
     */
    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new BusinessException(ErrorCode.NOT_FOUND, "策略不存在: " + id);
        }
        repository.deleteById(id);
    }

    private SavedStrategyDetailDto toDetail(BacktestStrategyEntity e) {
        try {
            ScreenerCriteriaDto criteria = objectMapper.readValue(e.getCriteriaJson(), ScreenerCriteriaDto.class);
            BacktestConfigDto config = objectMapper.readValue(e.getConfigJson(), BacktestConfigDto.class);
            BacktestResultDto result = e.getResultJson() != null
                    ? objectMapper.readValue(e.getResultJson(), BacktestResultDto.class)
                    : null;
            return new SavedStrategyDetailDto(e.getId(), e.getName(), criteria, config, result,
                    e.getCreatedAt(), e.getUpdatedAt());
        } catch (JsonProcessingException ex) {
            throw new BusinessException(ErrorCode.INTERNAL_ERROR, "策略反序列化失败: " + ex.getMessage(), ex);
        }
    }
}
