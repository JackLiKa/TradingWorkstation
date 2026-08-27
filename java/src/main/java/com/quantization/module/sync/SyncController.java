package com.quantization.module.sync;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.sync.dto.SyncRequestDto;
import com.quantization.module.sync.dto.SyncStatusDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 数据同步 Controller，提供启动同步、查询状态和取消同步的接口。
 */
@Tag(name = "数据同步 sync")
@RestController
@RequestMapping("/api/sync")
public class SyncController {

    private final SyncService syncService;

    public SyncController(SyncService syncService) {
        this.syncService = syncService;
    }

    /**
     * 启动数据同步任务。
     *
     * @param request 同步请求参数
     * @return 同步状态
     */
    @Operation(summary = "启动同步任务")
    @PostMapping("/run")
    public ApiResponse<SyncStatusDto> run(@RequestBody SyncRequestDto request) {
        return ApiResponse.ok(syncService.start(request));
    }

    /**
     * 查询当前同步任务状态。
     *
     * @return 同步状态
     */
    @Operation(summary = "查询同步状态")
    @GetMapping("/status")
    public ApiResponse<SyncStatusDto> status() {
        return ApiResponse.ok(syncService.currentStatus());
    }

    /**
     * 取消正在运行的同步任务。
     *
     * @return 取消后的同步状态
     */
    @Operation(summary = "取消同步任务")
    @PostMapping("/cancel")
    public ApiResponse<SyncStatusDto> cancel() {
        return ApiResponse.ok(syncService.cancel());
    }
}
