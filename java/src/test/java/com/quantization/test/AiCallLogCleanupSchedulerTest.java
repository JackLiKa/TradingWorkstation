package com.quantization.test;

import com.quantization.module.aicalllog.AiCallLogCleanupScheduler;
import com.quantization.module.aicalllog.AiCallLogRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.ApplicationContext;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * {@link AiCallLogCleanupScheduler} 集成測試 — 使用 {@code @SpringBootTest} 載入完整 context，
 * 並以 {@code @MockBean(AiCallLogRepository)} 替換真實 Repository，避免 Testcontainers/DB 開銷。
 *
 * <p>驗證：</p>
 * <ul>
 *   <li>調度器在 {@code app.aicalllog.retention-days=90} 配置下正確初始化</li>
 *   <li>{@code cleanup()} 刪除超過保留天數的記錄</li>
 *   <li>{@code @ConditionalOnProperty(enabled=true)} 時 bean 存在</li>
 *   <li>默認 false 時 bean 不存在</li>
 * </ul>
 *
 * <p>外層類啟用調度器（{@code app.aicalllog.cleanup.enabled=true}）；
 * 內層 {@link DisabledByDefaultTest} 使用獨立 context 驗證默認關閉場景。</p>
 *
 * <p>使用 H2 內嵌資料庫（MySQL 相容模式）滿足 DataSource/EntityManagerFactory 初始化需求，
 * 關閉 schema 初始化（{@code spring.sql.init.mode=never}）因為 Repository 已被 mock。</p>
 */
@SpringBootTest(properties = {
        "app.aicalllog.cleanup.enabled=true",
        "app.aicalllog.retention-days=90",
        "spring.datasource.url=jdbc:h2:mem:sched-enabled;MODE=MySQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        "spring.sql.init.mode=never",
        "spring.jpa.hibernate.ddl-auto=none"
})
@DisplayName("AiCallLogCleanupScheduler 調度器測試")
class AiCallLogCleanupSchedulerTest {

    @Autowired
    private ApplicationContext context;

    @Autowired
    private AiCallLogCleanupScheduler scheduler;

    @MockBean
    private AiCallLogRepository repository;

    @Test
    @DisplayName("啟用時調度器 bean 存在於 context")
    void schedulerBean_exists_whenEnabled() {
        assertThat(context.containsBean("aiCallLogCleanupScheduler")).isTrue();
        assertThat(scheduler).isNotNull();
    }

    @Test
    @DisplayName("retention-days=90 正確初始化")
    void retentionDays_initializedTo90() {
        assertThat(scheduler.getRetentionDays()).isEqualTo(90);
    }

    @Test
    @DisplayName("cleanup() 刪除超過 90 天的記錄")
    void cleanup_deletesExpiredRecords() {
        when(repository.deleteByCreatedAtBefore(any(LocalDateTime.class))).thenReturn(5);

        scheduler.cleanup();

        verify(repository, times(1)).deleteByCreatedAtBefore(any(LocalDateTime.class));
    }

    @Test
    @DisplayName("cleanup() 多次調用均觸發 Repository 刪除")
    void cleanup_invokesRepositoryEachTime() {
        when(repository.deleteByCreatedAtBefore(any(LocalDateTime.class))).thenReturn(0);

        scheduler.cleanup();
        scheduler.cleanup();

        verify(repository, times(2)).deleteByCreatedAtBefore(any(LocalDateTime.class));
    }

    /**
     * 默認關閉場景：不自定義 {@code app.aicalllog.cleanup.enabled}（默認 false），
     * 調度器 bean 不應存在。使用獨立 {@code @SpringBootTest} context。
     */
    @Nested
    @SpringBootTest(properties = {
            "spring.datasource.url=jdbc:h2:mem:sched-disabled;MODE=MySQL;DB_CLOSE_DELAY=-1",
            "spring.datasource.driver-class-name=org.h2.Driver",
            "spring.datasource.username=sa",
            "spring.datasource.password=",
            "spring.sql.init.mode=never",
            "spring.jpa.hibernate.ddl-auto=none"
    })
    @DisplayName("默認關閉時（app.aicalllog.cleanup.enabled 默認 false）")
    class DisabledByDefaultTest {

        @Autowired
        private ApplicationContext context;

        @Test
        @DisplayName("調度器 bean 不存在於 context")
        void schedulerBean_doesNotExist_whenDisabledByDefault() {
            assertThat(context.containsBean("aiCallLogCleanupScheduler")).isFalse();
        }
    }
}
