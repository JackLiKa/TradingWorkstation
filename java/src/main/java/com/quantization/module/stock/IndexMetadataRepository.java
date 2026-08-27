package com.quantization.module.stock;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 指數元數據 JPA Repository。
 */
@Repository
public interface IndexMetadataRepository extends JpaRepository<IndexMetadataEntity, Long> {

    /** 查詢全部指數元數據，按分類代碼排序。 */
    List<IndexMetadataEntity> findAllByOrderByCategoryCodeAscCodeAsc();

    /** 按分類英文代碼查詢指數列表。 */
    List<IndexMetadataEntity> findByCategoryCodeOrderByCodeAsc(String categoryCode);
}
