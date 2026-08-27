package com.quantization.module.backtest.dto;

import com.quantization.module.screener.dto.ScreenerCriteriaDto;
import java.time.LocalDate;

/**
 * Walk-forward 回測配置 DTO，用於樣本外驗證。
 *
 * <p>Walk-forward 驗證將歷史數據分為多個 train/test 窗口，
 * 在 train 段優化策略參數，在 test 段驗證樣本外表現。
 * 這是防止過擬合的關鍵方法論。</p>
 *
 * @param criteria    選股條件（train 段用於優化，test 段用於驗證）
 * @param config      回測配置
 * @param trainStart  訓練段起始日期
 * @param trainEnd    訓練段結束日期
 * @param testStart   測試段起始日期
 * @param testEnd     測試段結束日期
 * @param nFolds      滾動窗口數（0=單次 train/test，>0=滾動 walk-forward）
 */
public record WalkForwardConfigDto(
        ScreenerCriteriaDto criteria,
        BacktestConfigDto config,
        LocalDate trainStart,
        LocalDate trainEnd,
        LocalDate testStart,
        LocalDate testEnd,
        int nFolds
) {
    /** 有效折數（永遠 ≥1）。 */
    public int effectiveNFolds() {
        return nFolds > 0 ? nFolds : 1;
    }
}
