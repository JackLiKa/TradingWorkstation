package com.quantization.module.stock;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * 指數元數據實體 — 代碼/名稱/分類，對應 index_metadata 表。
 * 數據來源：ingestion/index_list.json（10 大類別，~80 個指數）。
 */
@Entity
@Table(name = "index_metadata")
public class IndexMetadataEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "code", nullable = false, length = 16, unique = true)
    private String code;

    @Column(name = "name", nullable = false, length = 64)
    private String name;

    @Column(name = "category", nullable = false, length = 32)
    private String category;

    @Column(name = "category_code", nullable = false, length = 32)
    private String categoryCode;

    @Column(name = "source", nullable = false, length = 32)
    private String source = "baostock";

    @Column(name = "created_at", updatable = false, insertable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", updatable = false, insertable = false)
    private LocalDateTime updatedAt;

    // --- Getters / Setters ---

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category; }

    public String getCategoryCode() { return categoryCode; }
    public void setCategoryCode(String categoryCode) { this.categoryCode = categoryCode; }

    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
