package com.quantization.module.aicalllog;

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
 * AI 調用日誌實體 — 記錄每一次 AI 階段調用的完整輸入輸出和評委結果。
 * 用於 Agent Dashboard 可觀測性：分數趨勢、調用鏈追蹤、IO 審計。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "ai_call_log")
public class AiCallLogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** 優化迭代輪次（從 1 開始） */
    @Column(name = "iteration", nullable = false)
    private Integer iteration;

    /** 階段標識：market_news / industry_analysis / market_analysis / strategy_generation / backtest_reflection / prompt_generation / judge */
    @Column(name = "stage_name", nullable = false, length = 64)
    private String stageName;

    /** 階段顯示名稱（中文） */
    @Column(name = "stage_display_name", length = 128)
    private String stageDisplayName;

    /** LLM 提供商：qoder / devin / none */
    @Column(name = "provider", length = 32)
    private String provider;

    /** 模型名稱 */
    @Column(name = "model_name", length = 64)
    private String modelName;

    /** 標準化 JSON 輸入（含 system_prompt + user_prompt + context） */
    @Column(name = "input_json", columnDefinition = "LONGTEXT")
    private String inputJson;

    /** AI 原始輸出文本 */
    @Column(name = "output_text", columnDefinition = "LONGTEXT")
    private String outputText;

    /** 標準化 JSON 輸出（解析後的結構化結果，若可解析） */
    @Column(name = "output_json", columnDefinition = "LONGTEXT")
    private String outputJson;

    /** 評委評分（0-100） */
    @Column(name = "judge_score")
    private Double judgeScore;

    /** 評委是否通過 */
    @Column(name = "judge_passed")
    private Boolean judgePassed;

    /** 評委反饋 */
    @Column(name = "judge_feedback", columnDefinition = "TEXT")
    private String judgeFeedback;

    /** 嘗試次數（含重試） */
    @Column(name = "attempts")
    private Integer attempts;

    /** 執行耗時（毫秒） */
    @Column(name = "duration_ms")
    private Integer durationMs;

    /** 異常信息，無異常時為 null */
    @Column(name = "error", columnDefinition = "TEXT")
    private String error;

    /** 創建時間 */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
