package com.quantization.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;

import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 异步线程池配置 — 用于 Dashboard 并行加载等场景。
 * 使用固定线程池，避免无限制创建线程。
 */
@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean("asyncExecutor")
    public Executor asyncExecutor() {
        return Executors.newFixedThreadPool(8, r -> {
            Thread t = new Thread(r, "dashboard-async");
            t.setDaemon(true);
            return t;
        });
    }
}
