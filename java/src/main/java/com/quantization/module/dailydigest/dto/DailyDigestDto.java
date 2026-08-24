package com.quantization.module.dailydigest.dto;

import com.fasterxml.jackson.annotation.JsonRawValue;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 當日市場摘要 DTO — 用於 API 返回。
 */
public record DailyDigestDto(
        Long id,
        LocalDate tradeDate,
        String marketOverview,
        String sectorHighlights,
        String newsDigest,
        String sentiment,
        List<String> keyEvents,
        List<String> dataSources,
        LocalDateTime generatedAt
) {}
