package com.quantization.module.system;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.system.dto.DatabaseConfigDto;
import com.quantization.module.system.dto.DatabaseConfigUpdateDto;
import com.quantization.module.system.dto.SystemHealthDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 系统 Controller，提供数据库健康检查和配置管理接口。
 */
@Tag(name = "系统 system")
@RestController
@RequestMapping("/api/system")
public class SystemController {

    private final SystemService systemService;
    private final NotificationService notificationService;

    public SystemController(SystemService systemService, NotificationService notificationService) {
        this.systemService = systemService;
        this.notificationService = notificationService;
    }

    /**
     * 数据库健康检查（连接 + 表结构校验）。
     *
     * @return 系统健康状态 DTO
     */
    @Operation(summary = "数据库健康检查（连接 + 表结构校验）")
    @GetMapping("/health")
    public ApiResponse<SystemHealthDto> health() {
        return ApiResponse.ok(systemService.health());
    }

    /**
     * 获取当前数据库配置（不含密码）。
     *
     * @return 数据库配置 DTO
     */
    @Operation(summary = "当前数据库配置（不含密码）")
    @GetMapping("/database")
    public ApiResponse<DatabaseConfigDto> currentConfig() {
        return ApiResponse.ok(systemService.currentConfig());
    }

    /**
     * 更新数据库配置（写入 .env，重启后生效）。
     *
     * @param update 配置更新请求
     * @return 更新后的数据库配置 DTO
     */
    @Operation(summary = "更新数据库配置（写入 .env，重启后生效）")
    @PutMapping("/database")
    public ApiResponse<DatabaseConfigDto> updateConfig(@Valid @RequestBody DatabaseConfigUpdateDto update) {
        return ApiResponse.ok(systemService.updateConfig(update));
    }

    /**
     * 測試通知服務（郵件/Webhook 配置驗證）。
     *
     * @return 通知服務狀態與測試結果
     */
    @Operation(summary = "測試通知服務（郵件/Webhook 配置驗證）")
    @GetMapping("/notification/test")
    public ApiResponse<String> testNotification() {
        return ApiResponse.ok(notificationService.testNotification());
    }
}
