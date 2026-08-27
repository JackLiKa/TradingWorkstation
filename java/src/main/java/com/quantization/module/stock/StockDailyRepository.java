package com.quantization.module.stock;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * 股票日线 JPA Repository，继承标准 CRUD 和自定义查询接口。
 */
@Repository
public interface StockDailyRepository extends JpaRepository<StockDailyEntity, Long>, StockDailyRepositoryCustom {
}
