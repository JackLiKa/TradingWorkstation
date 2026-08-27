package com.quantization.module.snapshot;

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

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 行情分析預計算快照實體。
 * 由 ingestion/precompute_market_snapshot.py 在數據更新後寫入，
 * 前端直接加載快照，無需實時計算。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "market_analysis_snapshot")
public class MarketSnapshotEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** 交易日 */
    @Column(name = "trade_date", nullable = false)
    private LocalDate tradeDate;

    /** 快照類型：market_overview / industry_prosperity / rotation_signals / market_breadth */
    @Column(name = "snapshot_type", nullable = false, length = 50)
    private String snapshotType;

    /** 預計算的 JSON 快照數據 */
    @Column(name = "snapshot_data", columnDefinition = "JSON", nullable = false)
    private String snapshotData;

    /** 計算時間 */
    @Column(name = "computed_at", nullable = false)
    private LocalDateTime computedAt;

    /** 快照格式版本 */
    @Column(name = "data_version", nullable = false, length = 20)
    private String dataVersion;
}
