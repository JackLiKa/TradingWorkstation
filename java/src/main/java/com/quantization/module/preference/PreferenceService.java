package com.quantization.module.preference;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.quantization.config.properties.AppProperties;
import com.quantization.module.preference.dto.UserPreferenceDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;

/**
 * 用户偏好持久化服务 — 主存储为 MySQL（{@link PreferenceRepository}），
 * 降级存储为 JSON 文件（路径由 {@code app.preference.path} 配置，环境变量 {@code PREFERENCE_PATH}）。
 * <p>
 * 用于增强功能：选股预设、自选股、K线指标配置、排序偏好等。
 * <p>
 * 当 DB 操作抛出异常时，自动降级到文件存储，保证服务可用性。
 * 文件写入采用临时文件 + 原子移动（{@link StandardCopyOption#ATOMIC_MOVE}），并使用 synchronized
 * 防止并发写入冲突。
 */
@Slf4j
@Service
public class PreferenceService {

    /** 默认用户标识（当前单用户场景）。 */
    private static final String DEFAULT_USER_ID = "default";

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final PreferenceRepository repository;
    private final Path preferencePath;

    /**
     * @param repository 偏好 JPA Repository（主存储）
     * @param properties 应用配置（提供文件降级路径）
     */
    public PreferenceService(PreferenceRepository repository, AppProperties properties) {
        this.repository = repository;
        String configured = properties.getPreference().getPath();
        Path resolved = Paths.get(configured);
        this.preferencePath = resolved.isAbsolute()
                ? resolved
                : Paths.get(System.getProperty("user.dir")).resolve(resolved);
    }

    /**
     * 加载用户偏好：优先从 DB 读取，DB 不可用时降级到文件。
     * 文件不存在或读取失败时返回默认空偏好。
     *
     * @return 用户偏好 DTO
     */
    public UserPreferenceDto load() {
        try {
            return loadFromDb();
        } catch (Exception e) {
            log.warn("[preference] DB 读取失败，降级到文件存储：{}", e.getMessage());
            return loadFromFile();
        }
    }

    /**
     * 保存用户偏好：优先写入 DB，DB 不可用时降级到文件（临时文件 + 原子移动）。
     *
     * @param preference 用户偏好 DTO
     * @return 保存的用户偏好 DTO
     */
    public UserPreferenceDto save(UserPreferenceDto preference) {
        try {
            return saveToDb(preference);
        } catch (Exception e) {
            log.warn("[preference] DB 写入失败，降级到文件存储：{}", e.getMessage());
            return saveToFile(preference);
        }
    }

    // ===== DB 主存储 =====

    private UserPreferenceDto loadFromDb() {
        PreferenceEntity entity = repository.findByUserId(DEFAULT_USER_ID).orElse(null);
        if (entity == null || entity.getPreferenceJson() == null) {
            return UserPreferenceDto.empty();
        }
        try {
            return objectMapper.readValue(entity.getPreferenceJson(), UserPreferenceDto.class);
        } catch (IOException e) {
            log.warn("[preference] DB JSON 反序列化失败：{}", e.getMessage());
            return UserPreferenceDto.empty();
        }
    }

    private UserPreferenceDto saveToDb(UserPreferenceDto preference) {
        String json;
        try {
            json = objectMapper.writeValueAsString(preference);
        } catch (IOException e) {
            throw new RuntimeException("偏好序列化失败", e);
        }
        LocalDateTime now = LocalDateTime.now();
        PreferenceEntity entity = repository.findByUserId(DEFAULT_USER_ID).orElse(null);
        if (entity == null) {
            entity = new PreferenceEntity();
            entity.setUserId(DEFAULT_USER_ID);
            entity.setPreferenceJson(json);
            entity.setCreatedAt(now);
            entity.setUpdatedAt(now);
        } else {
            entity.setPreferenceJson(json);
            entity.setUpdatedAt(now);
        }
        repository.save(entity);
        return preference;
    }

    // ===== 文件降级存储 =====

    private UserPreferenceDto loadFromFile() {
        if (!Files.exists(preferencePath)) {
            return UserPreferenceDto.empty();
        }
        try {
            return objectMapper.readValue(Files.readAllBytes(preferencePath), UserPreferenceDto.class);
        } catch (IOException e) {
            log.warn("[preference] 文件读取失败：{}", e.getMessage());
            return UserPreferenceDto.empty();
        }
    }

    private synchronized UserPreferenceDto saveToFile(UserPreferenceDto preference) {
        Path tempPath = preferencePath.resolveSibling(preferencePath.getFileName() + ".tmp");
        try {
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(tempPath.toFile(), preference);
            Files.move(tempPath, preferencePath,
                    StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            return preference;
        } catch (IOException e) {
            log.error("[preference] 文件保存失败", e);
            try {
                Files.deleteIfExists(tempPath);
            } catch (IOException ignored) {
            }
            return preference;
        }
    }
}
