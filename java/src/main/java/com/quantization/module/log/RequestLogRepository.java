package com.quantization.module.log;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;

@Repository
public interface RequestLogRepository extends JpaRepository<RequestLogEntity, Long> {

    /** 按時間倒序分頁查詢 */
    Page<RequestLogEntity> findAllByOrderByCreatedAtDesc(Pageable pageable);

    /** 按路徑前綴篩選 */
    Page<RequestLogEntity> findByRequestPathContainingOrderByCreatedAtDesc(String path, Pageable pageable);

    /** 按狀態碼篩選 */
    Page<RequestLogEntity> findByStatusCodeOrderByCreatedAtDesc(Integer statusCode, Pageable pageable);

    /** 按客戶端 IP 篩選 */
    Page<RequestLogEntity> findByClientIpOrderByCreatedAtDesc(String clientIp, Pageable pageable);

    /** 清理超過指定時間的日誌（滑動窗口） */
    @Modifying
    @Query("DELETE FROM RequestLogEntity e WHERE e.createdAt < :before")
    int deleteByCreatedAtBefore(@Param("before") LocalDateTime before);
}
