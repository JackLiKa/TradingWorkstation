package com.quantization.test;

import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;
import org.testcontainers.DockerClientFactory;

/**
 * JUnit 5 {@link ExecutionCondition} — 當 Docker 守護進程不可用時跳過測試。
 *
 * <p>用於 Testcontainers 集成測試：在 CI/本地環境中 Docker 未安裝或未啟動時，
 * 自動跳過而非報錯，保證 {@code mvn test} 不會因環境問題而失敗。</p>
 *
 * <p>用法：在測試類上標註 {@code @ExtendWith(EnabledIfDockerAvailable.class)}。</p>
 */
public class EnabledIfDockerAvailable implements ExecutionCondition {

    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context) {
        try {
            // 嘗試獲取 Docker 客戶端並檢查連接；失敗則跳過測試
            DockerClientFactory.instance().client().pingCmd().exec();
            return ConditionEvaluationResult.enabled("Docker 守護進程可用");
        } catch (Throwable e) {
            return ConditionEvaluationResult.disabled(
                    "Docker 不可用（" + e.getMessage() + "），跳過 Testcontainers 測試");
        }
    }
}
