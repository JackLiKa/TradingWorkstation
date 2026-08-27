package com.quantization.module.aicalllog;

import com.quantization.module.aicalllog.dto.AiCallLogDto;
import com.quantization.module.aicalllog.dto.AiCallLogRequest;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * AI 調用日誌服務 — 提供日誌記錄、分頁查詢、評分趨勢聚合。
 */
@Service
public class AiCallLogService {

    private final AiCallLogRepository repository;

    public AiCallLogService(AiCallLogRepository repository) {
        this.repository = repository;
    }

    /** 記錄一條 AI 調用日誌 */
    public AiCallLogDto log(AiCallLogRequest request) {
        AiCallLogEntity entity = new AiCallLogEntity();
        entity.setIteration(request.iteration() != null ? request.iteration() : 0);
        entity.setStageName(request.stageName() != null ? request.stageName() : "unknown");
        entity.setStageDisplayName(request.stageDisplayName());
        entity.setProvider(request.provider());
        entity.setModelName(request.modelName());
        entity.setInputJson(request.inputJson());
        entity.setOutputText(request.outputText());
        entity.setOutputJson(request.outputJson());
        entity.setJudgeScore(request.judgeScore());
        entity.setJudgePassed(request.judgePassed());
        entity.setJudgeFeedback(request.judgeFeedback());
        entity.setAttempts(request.attempts() != null ? request.attempts() : 1);
        entity.setDurationMs(request.durationMs() != null ? request.durationMs() : 0);
        entity.setError(request.error());
        entity.setCreatedAt(LocalDateTime.now());
        entity = repository.save(entity);
        return toDto(entity);
    }

    /** 分頁查詢全部日誌 */
    public Page<AiCallLogDto> findAll(int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return repository.findAllByOrderByCreatedAtDesc(pageable).map(this::toDto);
    }

    /** 按階段分頁查詢 */
    public Page<AiCallLogDto> findByStage(String stageName, int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return repository.findByStageNameOrderByCreatedAtDesc(stageName, pageable).map(this::toDto);
    }

    /** 查詢某次迭代的全部階段日誌（調用鏈） */
    public List<AiCallLogDto> findByIteration(int iteration) {
        return repository.findByIterationOrderByStageNameAsc(iteration).stream()
                .map(this::toDto).toList();
    }

    /** 查詢最近 N 條日誌 */
    public List<AiCallLogDto> findRecent(int limit) {
        Pageable pageable = PageRequest.of(0, limit);
        return repository.findTopNByOrderByCreatedAtDesc(pageable).stream()
                .map(this::toDto).toList();
    }

    /** 評分趨勢數據（用於前端圖表） */
    public Map<String, Object> scoreTrend() {
        List<Object[]> rows = repository.scoreTrendByIteration();
        List<Map<String, Object>> trends = new ArrayList<>();
        for (Object[] row : rows) {
            Map<String, Object> point = new HashMap<>();
            point.put("iteration", row[0]);
            point.put("stageName", row[1]);
            point.put("avgScore", row[2]);
            point.put("maxScore", row[3]);
            point.put("minScore", row[4]);
            trends.add(point);
        }

        List<Object[]> iterScores = repository.iterationScoreSummary();
        List<Map<String, Object>> iterTrends = new ArrayList<>();
        for (Object[] row : iterScores) {
            Map<String, Object> point = new HashMap<>();
            point.put("iteration", row[0]);
            point.put("avgScore", row[1]);
            point.put("callCount", row[2]);
            iterTrends.add(point);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("stageTrends", trends);
        result.put("iterationTrends", iterTrends);
        result.put("stages", repository.findDistinctStageNames());
        result.put("maxIteration", repository.findMaxIteration());
        return result;
    }

    private AiCallLogDto toDto(AiCallLogEntity e) {
        return new AiCallLogDto(
                e.getId(), e.getIteration(), e.getStageName(), e.getStageDisplayName(),
                e.getProvider(), e.getModelName(), e.getInputJson(), e.getOutputText(),
                e.getOutputJson(), e.getJudgeScore(), e.getJudgePassed(), e.getJudgeFeedback(),
                e.getAttempts(), e.getDurationMs(), e.getError(), e.getCreatedAt()
        );
    }
}
