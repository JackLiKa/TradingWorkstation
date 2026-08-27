package com.quantization.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 异步线程池配置 — 按用途分离线程池，避免相互阻塞。
 * <ul>
 *   <li>{@code asyncExecutor}：Dashboard 并行加载等场景，8 线程</li>
 *   <li>{@code notificationExecutor}：通知推送（郵件/Webhook），4 線程</li>
 * </ul>
 * 使用固定线程池，避免无限制创建线程。
 */
@Configuration
@EnableAsync
@EnableScheduling
public class AsyncConfig {

    @Bean("asyncExecutor")
    public Executor asyncExecutor() {
        return Executors.newFixedThreadPool(8, r -> {
            Thread t = new Thread(r, "dashboard-async");
            t.setDaemon(true);
            return t;
        });
    }

    @Bean("notificationExecutor")
    public ExecutorService notificationExecutor() {
        return Executors.newFixedThreadPool(4, r -> {
            Thread t = new Thread(r, "notification-async");
            t.setDaemon(true);
            return t;
        });
    }
}
