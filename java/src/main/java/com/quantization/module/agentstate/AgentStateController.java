package com.quantization.module.agentstate;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.agentstate.dto.AgentStateDto;
import com.quantization.module.agentstate.dto.AgentStateRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Agent 狀態 Controller — 提供狀態持久化和恢復 API。
 */
@Tag(name = "Agent 狀態 agentstate")
@RestController
@RequestMapping("/api/agentstate")
public class AgentStateController {

    private final AgentStateService service;

    public AgentStateController(AgentStateService service) {
        this.service = service;
    }

    /** 保存 Agent 狀態（Agent 服務每輪結束後調用） */
    @Operation(summary = "保存 Agent 狀態")
    @PostMapping
    public ApiResponse<AgentStateDto> save(@RequestBody AgentStateRequest request) {
        return ApiResponse.ok(service.save(request));
    }

    /** 讀取 Agent 狀態（Agent 服務啟動時調用） */
    @Operation(summary = "讀取 Agent 狀態")
    @GetMapping
    public ApiResponse<AgentStateDto> load(@RequestParam(required = false, defaultValue = "default") String stateKey) {
        return ApiResponse.ok(service.load(stateKey));
    }
}
