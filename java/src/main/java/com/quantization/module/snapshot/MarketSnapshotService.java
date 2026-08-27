package com.quantization.module.snapshot;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 行情快照服務 — 讀取預計算的行情分析快照。
 *
 * 快照由 ingestion/precompute_market_snapshot.py 在數據更新後寫入，
 * 本服務負責查詢並返回 JSON 數據，前端直接渲染，無需實時計算。
 */
@Service
public class MarketSnapshotService {

    private static final Logger log = LoggerFactory.getLogger(MarketSnapshotService.class);
    private static final ObjectMapper objectMapper = new ObjectMapper();

    private final MarketSnapshotRepository repository;

    public MarketSnapshotService(MarketSnapshotRepository repository) {
        this.repository = repository;
    }

    /**
     * 獲取指定交易日的全部快照。
     * 若 tradeDate 為 null，返回最新交易日的快照。
     */
    public Map<String, Object> getAllSnapshots(LocalDate tradeDate) {
        LocalDate targetDate = tradeDate;
        if (targetDate == null) {
            // 取最新交易日
            Optional<MarketSnapshotEntity> latest = repository
                    .findTopBySnapshotTypeOrderByTradeDateDesc("market_overview");
            if (latest.isEmpty()) {
                return Map.of("found", false, "message", "無可用快照數據");
            }
            targetDate = latest.get().getTradeDate();
        }

        List<MarketSnapshotEntity> snapshots = repository.findByTradeDate(targetDate);
        if (snapshots.isEmpty()) {
            return Map.of("found", false, "message", "交易日 " + targetDate + " 無快照數據",
                    "trade_date", targetDate.toString());
        }

        Map<String, Object> result = new HashMap<>();
        result.put("found", true);
        result.put("trade_date", targetDate.toString());

        for (MarketSnapshotEntity snapshot : snapshots) {
            try {
                Object parsed = objectMapper.readValue(snapshot.getSnapshotData(), Object.class);
                result.put(snapshot.getSnapshotType(), parsed);
            } catch (JsonProcessingException e) {
                log.warn("解析快照 JSON 失敗 (type={}): {}", snapshot.getSnapshotType(), e.getMessage());
                result.put(snapshot.getSnapshotType(), snapshot.getSnapshotData());
            }
        }

        result.put("computed_at", snapshots.get(0).getComputedAt().toString());
        return result;
    }

    /**
     * 獲取指定類型的快照。
     */
    public Map<String, Object> getSnapshotByType(String snapshotType, LocalDate tradeDate) {
        LocalDate targetDate = tradeDate;
        if (targetDate == null) {
            Optional<MarketSnapshotEntity> latest = repository
                    .findTopBySnapshotTypeOrderByTradeDateDesc(snapshotType);
            if (latest.isEmpty()) {
                return Map.of("found", false, "message", "無 " + snapshotType + " 快照數據");
            }
            targetDate = latest.get().getTradeDate();
        }

        Optional<MarketSnapshotEntity> snapshot = repository
                .findByTradeDateAndSnapshotType(targetDate, snapshotType);
        if (snapshot.isEmpty()) {
            return Map.of("found", false, "message", "交易日 " + targetDate + " 無 " + snapshotType + " 快照");
        }

        Map<String, Object> result = new HashMap<>();
        result.put("found", true);
        result.put("trade_date", targetDate.toString());
        result.put("snapshot_type", snapshotType);
        result.put("computed_at", snapshot.get().getComputedAt().toString());
        try {
            result.put("data", objectMapper.readValue(snapshot.get().getSnapshotData(), Object.class));
        } catch (JsonProcessingException e) {
            result.put("data", snapshot.get().getSnapshotData());
        }
        return result;
    }

    /**
     * 獲取快照歷史日期列表（用於前端選擇歷史快照）。
     */
    public List<String> getSnapshotDates(String snapshotType, int limit) {
        List<MarketSnapshotEntity> records = repository
                .findTop10BySnapshotTypeOrderByTradeDateDesc(snapshotType);
        return records.stream()
                .limit(limit)
                .map(e -> e.getTradeDate().toString())
                .toList();
    }
}
