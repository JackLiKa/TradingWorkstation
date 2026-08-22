package com.quantization.module.preference;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * 用户偏好 JPA Repository — 提供按 userId 查询。
 */
@Repository
public interface PreferenceRepository extends JpaRepository<PreferenceEntity, Long> {

    /** 按用户标识查询偏好。 */
    Optional<PreferenceEntity> findByUserId(String userId);
}
