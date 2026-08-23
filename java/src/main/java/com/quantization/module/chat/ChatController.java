package com.quantization.module.chat;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.chat.dto.ChatConversationDto;
import com.quantization.module.chat.dto.ChatCreateRequest;
import com.quantization.module.chat.dto.ChatMessageDto;
import com.quantization.module.chat.dto.ChatSaveReplyRequest;
import com.quantization.module.chat.dto.ChatSendRequest;
import com.quantization.module.chat.dto.ChatUpdateRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * AI 聊天 Controller — 提供对话和消息的 CRUD API。
 * 对话持久化存储在 MySQL，支持历史对话延续。
 * AI 回复由 Agent 服务（端口 8100）流式生成，完成后通过 /reply 端点保存。
 */
@Tag(name = "AI 聊天 chat")
@RestController
@RequestMapping("/api/chat")
public class ChatController {

    private final ChatService service;

    public ChatController(ChatService service) {
        this.service = service;
    }

    /** 创建新对话 */
    @Operation(summary = "创建新对话")
    @PostMapping("/conversations")
    public ApiResponse<ChatConversationDto> createConversation(@RequestBody ChatCreateRequest request) {
        return ApiResponse.ok(service.createConversation(request));
    }

    /** 列出全部对话 */
    @Operation(summary = "列出全部对话")
    @GetMapping("/conversations")
    public ApiResponse<List<ChatConversationDto>> listConversations() {
        return ApiResponse.ok(service.listConversations());
    }

    /** 获取指定对话的消息列表 */
    @Operation(summary = "获取对话消息列表")
    @GetMapping("/conversations/{id}/messages")
    public ApiResponse<List<ChatMessageDto>> getMessages(@PathVariable Long id) {
        return ApiResponse.ok(service.getMessages(id));
    }

    /** 保存用户消息（前端发送消息时先保存，再调 Agent SSE 流式获取回复） */
    @Operation(summary = "保存用户消息")
    @PostMapping("/conversations/{id}/messages")
    public ApiResponse<ChatMessageDto> saveUserMessage(
            @PathVariable Long id,
            @RequestBody ChatSendRequest request) {
        return ApiResponse.ok(service.saveUserMessage(id, request));
    }

    /** 保存 AI 回复（Agent 流式完成后调用） */
    @Operation(summary = "保存 AI 回复")
    @PostMapping("/conversations/{id}/reply")
    public ApiResponse<ChatMessageDto> saveAssistantReply(
            @PathVariable Long id,
            @RequestBody ChatSaveReplyRequest request) {
        return ApiResponse.ok(service.saveAssistantReply(id, request));
    }

    /** 更新对话标题 */
    @Operation(summary = "更新对话标题")
    @PatchMapping("/conversations/{id}")
    public ApiResponse<ChatConversationDto> updateConversation(
            @PathVariable Long id,
            @RequestBody ChatUpdateRequest request) {
        return ApiResponse.ok(service.updateConversation(id, request));
    }

    /** 删除对话（级联删除消息） */
    @Operation(summary = "删除对话")
    @DeleteMapping("/conversations/{id}")
    public ApiResponse<Void> deleteConversation(@PathVariable Long id) {
        service.deleteConversation(id);
        return ApiResponse.ok(null);
    }
}
