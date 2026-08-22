package com.quantization.test;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.quantization.config.properties.AppProperties;
import com.quantization.module.preference.PreferenceEntity;
import com.quantization.module.preference.PreferenceRepository;
import com.quantization.module.preference.PreferenceService;
import com.quantization.module.preference.dto.UserPreferenceDto;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * PreferenceService 测试：验证 DB 主存储读写往返、JSON 合法性，以及 DB 异常时降级到文件存储。
 * 使用 Mockito mock {@link PreferenceRepository}，无需真实数据库。
 */
@DisplayName("PreferenceService DB 入库 + 文件降级")
class PreferenceServiceTest {

    @TempDir
    Path tempDir;

    private AppProperties appPropertiesWith(String path) {
        AppProperties props = new AppProperties();
        props.getPreference().setPath(path);
        return props;
    }

    /**
     * 创建一个有状态的 mock repository：findByUserId 返回最近一次 save 的实体（初始为空）。
     */
    private PreferenceRepository statefulMockRepository() {
        PreferenceRepository repo = mock(PreferenceRepository.class);
        PreferenceEntity[] holder = new PreferenceEntity[1];
        when(repo.findByUserId("default")).thenAnswer(inv -> Optional.ofNullable(holder[0]));
        when(repo.save(any(PreferenceEntity.class))).thenAnswer(inv -> {
            holder[0] = inv.getArgument(0);
            return holder[0];
        });
        return repo;
    }

    @Test
    @DisplayName("load DB 无记录时返回空偏好")
    void load_returnsEmpty_whenNoDbRecord() {
        PreferenceRepository repo = mock(PreferenceRepository.class);
        when(repo.findByUserId("default")).thenReturn(Optional.empty());
        PreferenceService service = new PreferenceService(repo, appPropertiesWith(tempDir.resolve("ignored.json").toString()));

        UserPreferenceDto result = service.load();

        assertThat(result).isEqualTo(UserPreferenceDto.empty());
    }

    @Test
    @DisplayName("save 后 load 能通过 DB 往返还原偏好")
    void save_thenLoad_roundTripsViaDb() {
        PreferenceRepository repo = statefulMockRepository();
        PreferenceService service = new PreferenceService(repo, appPropertiesWith(tempDir.resolve("ignored.json").toString()));

        UserPreferenceDto original = new UserPreferenceDto(
                "2", 100, 90,
                java.util.List.of("sh.600000"),
                java.util.Map.of(),
                UserPreferenceDto.IndicatorConfigPreferenceDto.defaults(),
                "date"
        );
        service.save(original);

        UserPreferenceDto loaded = service.load();
        assertThat(loaded).isEqualTo(original);
    }

    @Test
    @DisplayName("save 写入 DB 的 JSON 内容合法且可反序列化")
    void save_producesValidJsonInDb() {
        PreferenceRepository repo = statefulMockRepository();
        PreferenceService service = new PreferenceService(repo, appPropertiesWith(tempDir.resolve("ignored.json").toString()));

        UserPreferenceDto original = UserPreferenceDto.empty();
        service.save(original);

        // 验证 repository.save 被调用且 JSON 可被 Jackson 反序列化
        verify(repo, atLeastOnce()).save(any(PreferenceEntity.class));
        PreferenceEntity saved = repo.findByUserId("default").orElseThrow();
        try {
            UserPreferenceDto parsed = new ObjectMapper().readValue(saved.getPreferenceJson(), UserPreferenceDto.class);
            assertThat(parsed).isEqualTo(original);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    @DisplayName("save 设置 createdAt / updatedAt 时间戳")
    void save_setsTimestamps() {
        PreferenceRepository repo = statefulMockRepository();
        PreferenceService service = new PreferenceService(repo, appPropertiesWith(tempDir.resolve("ignored.json").toString()));

        service.save(UserPreferenceDto.empty());

        PreferenceEntity saved = repo.findByUserId("default").orElseThrow();
        assertThat(saved.getCreatedAt()).isNotNull();
        assertThat(saved.getUpdatedAt()).isNotNull();
        assertThat(saved.getUserId()).isEqualTo("default");
    }

    @Test
    @DisplayName("DB 异常时 save 降级到文件存储")
    void save_fallsBackToFile_whenDbThrows() {
        Path path = tempDir.resolve("fallback.json");
        PreferenceRepository repo = mock(PreferenceRepository.class);
        when(repo.findByUserId("default")).thenThrow(new RuntimeException("DB down"));
        PreferenceService service = new PreferenceService(repo, appPropertiesWith(path.toString()));

        service.save(UserPreferenceDto.empty());

        assertThat(Files.exists(path)).isTrue();
    }

    @Test
    @DisplayName("DB 异常时 load 降级到文件存储")
    void load_fallsBackToFile_whenDbThrows() {
        Path path = tempDir.resolve("fallback-load.json");
        PreferenceRepository repo = mock(PreferenceRepository.class);
        when(repo.findByUserId("default")).thenThrow(new RuntimeException("DB down"));
        PreferenceService service = new PreferenceService(repo, appPropertiesWith(path.toString()));

        // 文件不存在 → 空偏好
        assertThat(service.load()).isEqualTo(UserPreferenceDto.empty());

        // 先通过降级写入文件，再读取验证往返
        UserPreferenceDto original = new UserPreferenceDto(
                "1", 50, 30,
                java.util.List.of(),
                java.util.Map.of(),
                UserPreferenceDto.IndicatorConfigPreferenceDto.defaults(),
                "score"
        );
        service.save(original);
        UserPreferenceDto loaded = service.load();
        assertThat(loaded).isEqualTo(original);
    }

    @Test
    @DisplayName("配置路径为相对路径时基于 user.dir 解析（降级场景验证）")
    void relativePath_resolvesAgainstUserDir() {
        String relativePath = "test-pref-relative.json";
        PreferenceRepository repo = mock(PreferenceRepository.class);
        when(repo.findByUserId("default")).thenThrow(new RuntimeException("DB down"));
        PreferenceService service = new PreferenceService(repo, appPropertiesWith(relativePath));
        Path userDir = Path.of(System.getProperty("user.dir"));
        Path expected = userDir.resolve(relativePath);

        try {
            Files.deleteIfExists(expected);
        } catch (Exception ignored) {
        }

        service.save(UserPreferenceDto.empty());
        assertThat(Files.exists(expected)).isTrue();

        try {
            Files.deleteIfExists(expected);
        } catch (Exception ignored) {
        }
    }
}
