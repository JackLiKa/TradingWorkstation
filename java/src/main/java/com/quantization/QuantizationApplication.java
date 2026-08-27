package com.quantization;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;

/**
 * 量化交易工作台后端入口类。
 * <p>
 * 启用 Spring Boot 自动配置与 Caffeine 缓存（{@code @EnableCaching}），
 * 为行情查询、选股、回测、指标计算与数据同步等模块提供 REST API 服务。
 * </p>
 */
@SpringBootApplication
@EnableCaching
public class QuantizationApplication {

    /**
     * 应用程序入口方法，启动 Spring Boot 容器。
     *
     * @param args 命令行参数，透传给 Spring Boot
     */
    public static void main(String[] args) {
        SpringApplication.run(QuantizationApplication.class, args);
    }
}
