package com.quantization.module.dailydigest;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.quantization.module.dailydigest.dto.DailyDigestDto;
import com.quantization.module.dailydigest.dto.DailyDigestRequest;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

/**
 * 當日市場摘要服務 — 提供摘要的生成、查詢和複用。
 * upsert 語義：同一交易日重複提交時更新已有記錄。
 */
@Service
public class DailyDigestService {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final DailyDigestRepository repository;

    public DailyDigestService(DailyDigestRepository repository) {
        this.repository = repository;
    }

    /** 保存或更新當日摘要（upsert，按 tradeDate） */
    public DailyDigestDto save(DailyDigestRequest request) {
        LocalDate tradeDate = request.tradeDate();
        Optional<DailyDigestEntity> existing = repository.findByTradeDate(tradeDate);
        DailyDigestEntity entity;
        if (existing.isPresent()) {
            entity = existing.get();
            entity.setMarketOverview(request.marketOverview());
            entity.setSectorHighlights(request.sectorHighlights());
            entity.setNewsDigest(request.newsDigest());
            entity.setSentiment(request.sentiment());
            entity.setKeyEventsJson(toJson(request.keyEvents()));
            entity.setDataSourcesJson(toJson(request.dataSources()));
            entity.setGeneratedAt(LocalDateTime.now());
        } else {
            entity = new DailyDigestEntity();
            entity.setTradeDate(tradeDate);
            entity.setMarketOverview(request.marketOverview());
            entity.setSectorHighlights(request.sectorHighlights());
            entity.setNewsDigest(request.newsDigest());
            entity.setSentiment(request.sentiment());
            entity.setKeyEventsJson(toJson(request.keyEvents()));
            entity.setDataSourcesJson(toJson(request.dataSources()));
            entity.setGeneratedAt(LocalDateTime.now());
        }
        entity = repository.save(entity);
        return toDto(entity);
    }

    /** 按交易日查詢摘要 */
    public DailyDigestDto findByTradeDate(LocalDate tradeDate) {
        return repository.findByTradeDate(tradeDate).map(this::toDto).orElse(null);
    }

    /** 查詢最近 N 條摘要 */
    public List<DailyDigestDto> findRecent(int limit) {
        return repository.findTopNByOrderByTradeDateDesc(PageRequest.of(0, limit)).stream()
                .map(this::toDto).toList();
    }

    private DailyDigestDto toDto(DailyDigestEntity e) {
        return new DailyDigestDto(
                e.getId(), e.getTradeDate(),
                e.getMarketOverview(), e.getSectorHighlights(),
                e.getNewsDigest(), e.getSentiment(),
                fromJson(e.getKeyEventsJson()), fromJson(e.getDataSourcesJson()),
                e.getGeneratedAt()
        );
    }

    private String toJson(List<String> list) {
        if (list == null || list.isEmpty()) return "[]";
        try {
            return MAPPER.writeValueAsString(list);
        } catch (JsonProcessingException e) {
            return "[]";
        }
    }

    private List<String> fromJson(String json) {
        if (json == null || json.isBlank()) return Collections.emptyList();
        try {
            return MAPPER.readValue(json, List.class);
        } catch (JsonProcessingException e) {
            return Collections.emptyList();
        }
    }
}
