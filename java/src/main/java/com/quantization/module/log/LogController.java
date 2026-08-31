package com.quantization.module.log;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.aicalllog.AiCallLogEntity;
import com.quantization.module.aicalllog.AiCallLogRepository;
import com.quantization.module.log.dto.LogEntry;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 日誌聚合 Controller — 統一查詢和推送所有來源的日誌。
 *
 * 端點：
 * - GET /api/logs/recent  — 獲取最近日誌（SWR 歷史加載）
 * - GET /api/logs/stream  — SSE 實時推送新日誌
 * - GET /api/logs/search  — 搜索篩選日誌
 */
@Slf4j
@Tag(name = "日誌 logs")
@RestController
@RequestMapping("/api/logs")
public class LogController {

    private final LogMemoryStore logMemoryStore;
    private final RequestLogRepository requestLogRepository;
    private final AiCallLogRepository aiCallLogRepository;
    private final ExecutorService sseExecutor = Executors.newCachedThreadPool();

    public LogController(LogMemoryStore logMemoryStore,
                         RequestLogRepository requestLogRepository,
                         AiCallLogRepository aiCallLogRepository) {
        this.logMemoryStore = logMemoryStore;
        this.requestLogRepository = requestLogRepository;
        this.aiCallLogRepository = aiCallLogRepository;
    }

    /** 獲取最近的統一日誌（從內存緩衝 + DB 補充） */
    @Operation(summary = "獲取最近日誌")
    @GetMapping("/recent")
    public ApiResponse<List<LogEntry>> recent(
            @RequestParam(defaultValue = "100") int limit,
            @RequestParam(required = false) String source,
            @RequestParam(required = false) String level,
            @RequestParam(required = false) String keyword) {

        List<LogEntry> entries = logMemoryStore.getRecent(limit);

        // 補充 AI 調用日誌（從 DB 查最近 N 條）
        if (source == null || source.isEmpty() || source.equals("ai")) {
            List<AiCallLogEntity> aiLogs = aiCallLogRepository.findAll(
                    PageRequest.of(0, Math.min(limit, 50))).getContent();
            for (AiCallLogEntity aiLog : aiLogs) {
                Map<String, Object> details = new LinkedHashMap<>();
                details.put("iteration", aiLog.getIteration());
                details.put("stageName", aiLog.getStageName());
                details.put("stageDisplayName", aiLog.getStageDisplayName());
                details.put("provider", aiLog.getProvider());
                details.put("modelName", aiLog.getModelName());
                details.put("judgeScore", aiLog.getJudgeScore());
                details.put("judgePassed", aiLog.getJudgePassed());
                details.put("durationMs", aiLog.getDurationMs());
                details.put("error", aiLog.getError());
                details.put("inputJson", aiLog.getInputJson());
                details.put("outputText", aiLog.getOutputText());

                String aiLevel = aiLog.getError() != null ? "ERROR"
                        : aiLog.getJudgePassed() != null && !aiLog.getJudgePassed() ? "WARN" : "INFO";
                String aiMessage = String.format("[迭代%d] %s — %s (%s) 評分:%s",
                        aiLog.getIteration(),
                        aiLog.getStageDisplayName() != null ? aiLog.getStageDisplayName() : aiLog.getStageName(),
                        aiLog.getProvider() != null ? aiLog.getProvider() : "unknown",
                        aiLog.getModelName() != null ? aiLog.getModelName() : "",
                        aiLog.getJudgeScore() != null ? String.format("%.1f", aiLog.getJudgeScore()) : "N/A");

                entries.add(new LogEntry(
                        "ai:" + aiLog.getId(),
                        "ai",
                        aiLevel,
                        aiMessage,
                        aiLog.getCreatedAt(),
                        details
                ));
            }
        }

        // 按時間倒序排序
        entries.sort(Comparator.comparing(LogEntry::timestamp).reversed());

        // 應用篩選
        if (source != null && !source.isEmpty()) {
            entries.removeIf(e -> !e.source().equals(source));
        }
        if (level != null && !level.isEmpty()) {
            entries.removeIf(e -> !e.level().equalsIgnoreCase(level));
        }
        if (keyword != null && !keyword.isEmpty()) {
            String kw = keyword.toLowerCase();
            entries.removeIf(e -> !e.message().toLowerCase().contains(kw)
                    && !e.source().toLowerCase().contains(kw));
        }

        // 限制返回數量
        if (entries.size() > limit) {
            entries = entries.subList(0, limit);
        }

        return ApiResponse.ok(entries);
    }

    /** SSE 實時推送新日誌 */
    @Operation(summary = "SSE 實時日誌推送")
    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream() {
        SseEmitter emitter = new SseEmitter(0L); // 無超時

        // 先發送當前緩衝區的最近 50 條作為初始數據
        try {
            List<LogEntry> recent = logMemoryStore.getRecent(50);
            for (LogEntry entry : recent) {
                emitter.send(SseEmitter.event()
                        .name("log")
                        .data(entry)
                        .id(entry.id()));
            }
        } catch (Exception e) {
            emitter.completeWithError(e);
            return emitter;
        }

        // 註冊訂閱者，新日誌到達時推送
        java.util.function.Consumer<LogEntry> subscriber = entry -> {
            try {
                emitter.send(SseEmitter.event()
                        .name("log")
                        .data(entry)
                        .id(entry.id()));
            } catch (Exception e) {
                emitter.completeWithError(e);
            }
        };
        logMemoryStore.subscribe(subscriber);

        // 客戶端斷開時清理
        emitter.onCompletion(() -> logMemoryStore.unsubscribe(subscriber));
        emitter.onTimeout(() -> logMemoryStore.unsubscribe(subscriber));
        emitter.onError(e -> logMemoryStore.unsubscribe(subscriber));

        return emitter;
    }

    /** 搜索歷史請求日誌（從 MySQL 查詢） */
    @Operation(summary = "搜索請求日誌")
    @GetMapping("/search")
    public ApiResponse<Map<String, Object>> search(
            @RequestParam(required = false) String path,
            @RequestParam(required = false) Integer statusCode,
            @RequestParam(required = false) String clientIp,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int size) {

        var pageable = PageRequest.of(page, size);
        var result = requestLogRepository.findAllByOrderByCreatedAtDesc(pageable);

        // 應用篩選
        var filtered = result.getContent().stream()
                .filter(e -> path == null || path.isEmpty() || e.getRequestPath().contains(path))
                .filter(e -> statusCode == null || statusCode.equals(e.getStatusCode()))
                .filter(e -> clientIp == null || clientIp.isEmpty() || clientIp.equals(e.getClientIp()))
                .toList();

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("content", filtered);
        response.put("totalElements", result.getTotalElements());
        response.put("totalPages", result.getTotalPages());
        response.put("currentPage", page);

        return ApiResponse.ok(response);
    }

    /** 獲取日誌來源分類統計 */
    @Operation(summary = "日誌分類統計")
    @GetMapping("/stats")
    public ApiResponse<Map<String, Object>> stats() {
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("memoryBufferSize", logMemoryStore.size());

        // 按來源統計內存緩衝中的數量
        List<LogEntry> all = logMemoryStore.getRecent(logMemoryStore.size());
        Map<String, Long> bySource = new LinkedHashMap<>();
        for (LogEntry e : all) {
            bySource.merge(e.source(), 1L, Long::sum);
        }
        stats.put("bySource", bySource);

        // 請求日誌總數
        stats.put("requestLogTotal", requestLogRepository.count());

        // AI 調用日誌總數
        stats.put("aiCallLogTotal", aiCallLogRepository.count());

        return ApiResponse.ok(stats);
    }
}
