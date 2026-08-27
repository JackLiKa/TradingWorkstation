package com.quantization.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * OpenAPI / Swagger 文档配置，定义 API 标题、版本和描述。
 */
@Configuration
public class OpenApiConfig {

    /**
     * 构建 OpenAPI 文档元信息。
     *
     * @return 包含标题、版本和描述的 OpenAPI 实例
     */
    @Bean
    public OpenAPI quantizationOpenAPI() {
        return new OpenAPI().info(new Info()
                .title("量化交易工作台 API")
                .version("1.0.0")
                .description("Java 21 + Spring Boot 后端，提供行情查询、选股、回测、指标计算与数据同步接口"));
    }
}
