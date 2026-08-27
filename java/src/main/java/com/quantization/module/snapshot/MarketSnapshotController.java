package com.quantization.module.snapshot;

import com.quantization.common.api.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.Map;

/**
 * 行情快照 Controller — 提供預計算的行情分析快照查詢接口。
 *
 * 快照由 ingestion 腳本在數據更新後預計算並寫入 market_analysis_snapshot 表，
 * 前端直接加載快照，無需實時計算，大幅提升加載速度。
 */
@Tag(name = "行情快照 snapshot")
@RestController
@RequestMapping("/api/snapshot")
public class MarketSnapshotController {

    private final MarketSnapshotService service;

    public MarketSnapshotController(MarketSnapshotService service) {
        this.service = service;
    }

    /**
     * 獲取指定交易日的全部行情快照（市場概覽 + 行業景氣度 + 輪動信號 + 市場廣度）。
     * 若不指定 tradeDate，返回最新交易日的快照。
     */
    @Operation(summary = "獲取全部行情快照（市場概覽+景氣度+輪動+廣度）")
    @GetMapping
    public ApiResponse<Map<String, Object>> getAllSnapshots(
            @RequestParam(required = false) LocalDate tradeDate) {
        return ApiResponse.ok(service.getAllSnapshots(tradeDate));
    }

    /**
     * 獲取指定類型的快照。
     * snapshotType: market_overview / industry_prosperity / rotation_signals / market_breadth
     */
    @Operation(summary = "按類型獲取行情快照")
    @GetMapping("/type")
    public ApiResponse<Map<String, Object>> getSnapshotByType(
            @RequestParam String snapshotType,
            @RequestParam(required = false) LocalDate tradeDate) {
        return ApiResponse.ok(service.getSnapshotByType(snapshotType, tradeDate));
    }

    /**
     * 獲取快照可用日期列表（用於前端選擇歷史快照）。
     */
    @Operation(summary = "獲取快照可用日期列表")
    @GetMapping("/dates")
    public ApiResponse<Map<String, Object>> getSnapshotDates(
            @RequestParam(defaultValue = "market_overview") String snapshotType,
            @RequestParam(defaultValue = "10") int limit) {
        return ApiResponse.ok(Map.of("dates", service.getSnapshotDates(snapshotType, limit)));
    }
}
