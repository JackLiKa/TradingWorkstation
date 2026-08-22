package com.quantization.test;

import com.quantization.module.preference.PreferenceEntity;
import com.quantization.module.preference.PreferenceRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * {@link PreferenceRepository} 集成測試 — 使用 Testcontainers 啟動真實 MySQL 8.0，
 * 驗證 {@code findByUserId}、save 往返、以及 userId 唯一約束的 upsert 行為。
 *
 * <p>替代原 Mockito mock 測試，確保 JPA 映射、SQL、唯一索引在真實資料庫下正確。</p>
 */
@DataJpaTest
@Testcontainers
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@ExtendWith(EnabledIfDockerAvailable.class)
@DisplayName("PreferenceRepository Testcontainers 集成測試")
class PreferenceRepositoryTest {

    @Container
    static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.0")
            .withDatabaseName("test_pref")
            .withUsername("test")
            .withPassword("test");

    @DynamicPropertySource
    static void overrideProps(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", mysql::getJdbcUrl);
        registry.add("spring.datasource.username", mysql::getUsername);
        registry.add("spring.datasource.password", mysql::getPassword);
    }

    @Autowired
    private PreferenceRepository repository;

    @Test
    @DisplayName("findByUserId 返回已保存的正確實體")
    void findByUserId_returnsSavedEntity() {
        PreferenceEntity entity = new PreferenceEntity();
        entity.setUserId("default");
        entity.setPreferenceJson("{\"version\":\"1\"}");
        entity.setCreatedAt(LocalDateTime.now());
        entity.setUpdatedAt(LocalDateTime.now());
        repository.save(entity);

        Optional<PreferenceEntity> found = repository.findByUserId("default");

        assertThat(found).isPresent();
        assertThat(found.get().getUserId()).isEqualTo("default");
        assertThat(found.get().getPreferenceJson()).isEqualTo("{\"version\":\"1\"}");
    }

    @Test
    @DisplayName("save 後 findByUserId 返回最新數據")
    void save_thenFindByUserId_returnsLatest() {
        // 初始保存
        PreferenceEntity entity = new PreferenceEntity();
        entity.setUserId("default");
        entity.setPreferenceJson("{\"v\":1}");
        entity.setCreatedAt(LocalDateTime.now());
        entity.setUpdatedAt(LocalDateTime.now());
        repository.save(entity);

        // 更新
        PreferenceEntity loaded = repository.findByUserId("default").orElseThrow();
        loaded.setPreferenceJson("{\"v\":2}");
        loaded.setUpdatedAt(LocalDateTime.now());
        repository.save(loaded);
        repository.flush();

        PreferenceEntity latest = repository.findByUserId("default").orElseThrow();
        assertThat(latest.getPreferenceJson()).isEqualTo("{\"v\":2}");
    }

    @Test
    @DisplayName("userId 唯一約束：save 兩次同 userId 應更新而非報錯")
    void save_twiceSameUserId_updatesWithoutError() {
        String userId = "default";
        LocalDateTime now = LocalDateTime.now();

        PreferenceEntity first = new PreferenceEntity();
        first.setUserId(userId);
        first.setPreferenceJson("{\"v\":1}");
        first.setCreatedAt(now);
        first.setUpdatedAt(now);
        repository.save(first);
        repository.flush();

        // 第二次：查找已有記錄並更新（模擬 PreferenceService 的 upsert 行為）
        PreferenceEntity existing = repository.findByUserId(userId).orElseThrow();
        existing.setPreferenceJson("{\"v\":2}");
        existing.setUpdatedAt(now);
        repository.save(existing);
        repository.flush();

        // 應只有一條記錄，且內容為最新
        assertThat(repository.count()).isEqualTo(1L);
        PreferenceEntity result = repository.findByUserId(userId).orElseThrow();
        assertThat(result.getPreferenceJson()).isEqualTo("{\"v\":2}");
    }
}
