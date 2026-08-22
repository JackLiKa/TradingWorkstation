package com.quantization.module.preference;

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
 * 用户偏好持久化实体 — 以 JSON 字符串存储 {@code UserPreferenceDto} 全量内容。
 * <p>
 * 替代原 preference.json 文件存储，解决多实例部署下文件存储失效问题。
 * {@code userId} 默认 "default"，未来可扩展多用户。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "user_preference")
public class PreferenceEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** 用户标识，默认 "default"。 */
    @Column(name = "user_id", unique = true, nullable = false, length = 64)
    private String userId;

    /** 偏好 JSON 全量内容。 */
    @Column(name = "preference_json", columnDefinition = "TEXT")
    private String preferenceJson;

    /** 创建时间。 */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** 更新时间。 */
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
