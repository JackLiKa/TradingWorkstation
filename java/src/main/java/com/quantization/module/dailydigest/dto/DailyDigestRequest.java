package com.quantization.module.dailydigest.dto;

import java.time.LocalDate;
import java.util.List;

/**
 * 當日市場摘要請求體 — Agent 服務提交生成的摘要。
 */
public record DailyDigestRequest(
        LocalDate tradeDate,
        String marketOverview,
        String sectorHighlights,
        String newsDigest,
        String sentiment,
        List<String> keyEvents,
        List<String> dataSources
) {}
