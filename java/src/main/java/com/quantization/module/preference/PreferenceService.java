package com.quantization.module.preference;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.quantization.module.preference.dto.UserPreferenceDto;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * 用户偏好持久化：以 JSON 文件存储于后端工作目录下 preference.json。
 * 用于增强功能：选股预设、自选股、K线指标配置、排序偏好等。
 */
@Slf4j
@Service
public class PreferenceService {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Path preferencePath;

    public PreferenceService() {
        this.preferencePath = Paths.get(System.getProperty("user.dir"), "preference.json");
    }

    /**
     * 加载用户偏好，文件不存在或读取失败时返回默认空偏好。
     *
     * @return 用户偏好 DTO
     */
    public UserPreferenceDto load() {
        if (!Files.exists(preferencePath)) {
            return UserPreferenceDto.empty();
        }
        try {
            return objectMapper.readValue(Files.readAllBytes(preferencePath), UserPreferenceDto.class);
        } catch (IOException e) {
            log.warn("[preference] 读取失败：{}", e.getMessage());
            return UserPreferenceDto.empty();
        }
    }

    /**
     * 保存用户偏好到 JSON 文件，失败时记录日志并返回原偏好。
     *
     * @param preference 用户偏好 DTO
     * @return 保存的用户偏好 DTO
     */
    public UserPreferenceDto save(UserPreferenceDto preference) {
        try {
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(preferencePath.toFile(), preference);
            return preference;
        } catch (IOException e) {
            log.error("[preference] 保存失败", e);
            return preference;
        }
    }
}
