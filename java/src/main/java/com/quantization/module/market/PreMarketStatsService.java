package com.quantization.module.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.quantization.module.stock.StockDailyEntity;
import com.quantization.module.stock.StockDailyRepositoryCustom;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDate;
import java.util.List;

@Slf4j
@Service
public class PreMarketStatsService {

    private final MarketPremarketStatsRepository statsRepository;
    private final StockDailyRepositoryCustom stockDailyRepository;
    private final ObjectMapper objectMapper;

    public PreMarketStatsService(MarketPremarketStatsRepository statsRepository,
                                  @Qualifier("stockDailyRepositoryImpl") StockDailyRepositoryCustom stockDailyRepository,
                                  ObjectMapper objectMapper) {
        this.statsRepository = statsRepository;
        this.stockDailyRepository = stockDailyRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public void computeAndSaveDailyStats() {
        LocalDate latestDate = stockDailyRepository.latestTradeDate();
        if (latestDate == null) {
            log.warn("[pre-market] 無最新交易日數據，跳過預計算");
            return;
        }
        log.info("[pre-market] 開始預計算 {} 的市場統計數據", latestDate);
        computeMovers(latestDate, 20);
        log.info("[pre-market] 預計算完成: tradeDate={}", latestDate);
    }

    private void computeMovers(LocalDate tradeDate, int limit) {
        try {
            statsRepository.deleteByDateAndType(tradeDate, "movers");
            statsRepository.flush();

            List<StockDailyEntity> movers = stockDailyRepository.latestMovers(limit);
            for (int i = 0; i < movers.size(); i++) {
                StockDailyEntity e = movers.get(i);
                MarketPremarketStatsEntity stat = new MarketPremarketStatsEntity();
                stat.setTradeDate(tradeDate);
                stat.setStatType("movers");
                stat.setStatKey(e.getCode());
                stat.setRank(i + 1);

                String value = objectMapper.writeValueAsString(new MoverData(
                        e.getCode(),
                        e.getClosePrice() != null ? e.getClosePrice().doubleValue() : null,
                        e.getPctChange() != null ? e.getPctChange().doubleValue() : null,
                        e.getVolume()
                ));
                stat.setStatValue(value);
                statsRepository.save(stat);
            }
            log.info("[pre-market] 波動排行預計算完成: {} 條", movers.size());
        } catch (Exception e) {
            log.error("[pre-market] 波動排行預計算失敗", e);
        }
    }

    @Transactional(propagation = org.springframework.transaction.annotation.Propagation.REQUIRES_NEW, readOnly = true)
    public List<MarketPremarketStatsEntity> getMovers(LocalDate tradeDate, int limit) {
        List<MarketPremarketStatsEntity> all = statsRepository.findByTradeDateAndStatTypeOrderByRankAsc(tradeDate, "movers");
        return all.size() > limit ? all.subList(0, limit) : all;
    }

    private record MoverData(String code, Double closePrice, Double pctChange, Long volume) {}
}
