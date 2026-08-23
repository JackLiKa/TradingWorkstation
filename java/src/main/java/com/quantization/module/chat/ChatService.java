package com.quantization.module.chat;

import com.quantization.module.chat.dto.ChatConversationDto;
import com.quantization.module.chat.dto.ChatCreateRequest;
import com.quantization.module.chat.dto.ChatMessageDto;
import com.quantization.module.chat.dto.ChatSaveReplyRequest;
import com.quantization.module.chat.dto.ChatSendRequest;
import com.quantization.module.chat.dto.ChatUpdateRequest;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 聊天服务 — 提供对话和消息的 CRUD 操作。
 * 对话归属单用户（user_id='default'），支持历史对话延续。
 */
@Service
public class ChatService {

    private static final String DEFAULT_USER_ID = "default";

    private final ChatConversationRepository conversationRepo;
    private final ChatMessageRepository messageRepo;

    public ChatService(ChatConversationRepository conversationRepo, ChatMessageRepository messageRepo) {
        this.conversationRepo = conversationRepo;
        this.messageRepo = messageRepo;
    }

    /** 创建新对话 */
    public ChatConversationDto createConversation(ChatCreateRequest request) {
        ChatConversationEntity entity = new ChatConversationEntity();
        entity.setUserId(DEFAULT_USER_ID);
        entity.setTitle(request.title() != null ? request.title() : "新对话");
        entity.setProvider(request.provider());
        LocalDateTime now = LocalDateTime.now();
        entity.setCreatedAt(now);
        entity.setUpdatedAt(now);
        entity = conversationRepo.save(entity);
        return toConversationDto(entity);
    }

    /** 列出全部对话（按更新时间倒序） */
    public List<ChatConversationDto> listConversations() {
        return conversationRepo.findByUserIdOrderByUpdatedAtDesc(DEFAULT_USER_ID).stream()
                .map(this::toConversationDto)
                .toList();
    }

    /** 获取指定对话的消息列表（按时间正序） */
    public List<ChatMessageDto> getMessages(Long conversationId) {
        return messageRepo.findByConversationIdOrderByCreatedAtAsc(conversationId).stream()
                .map(this::toMessageDto)
                .toList();
    }

    /** 保存用户消息 */
    public ChatMessageDto saveUserMessage(Long conversationId, ChatSendRequest request) {
        ChatMessageEntity entity = new ChatMessageEntity();
        entity.setConversationId(conversationId);
        entity.setRole("user");
        entity.setContent(request.content());
        entity.setCreatedAt(LocalDateTime.now());
        entity = messageRepo.save(entity);

        // 更新对话的 updated_at
        updateConversationTimestamp(conversationId);

        // 如果对话标题是默认的"新对话"，用用户消息前 30 字作为标题
        conversationRepo.findById(conversationId).ifPresent(conv -> {
            if ("新对话".equals(conv.getTitle())) {
                String title = request.content().length() > 30
                        ? request.content().substring(0, 30) + "..."
                        : request.content();
                conv.setTitle(title);
                conversationRepo.save(conv);
            }
        });

        return toMessageDto(entity);
    }

    /** 保存 AI 回复 */
    public ChatMessageDto saveAssistantReply(Long conversationId, ChatSaveReplyRequest request) {
        ChatMessageEntity entity = new ChatMessageEntity();
        entity.setConversationId(conversationId);
        entity.setRole("assistant");
        entity.setContent(request.content());
        entity.setProvider(request.provider());
        entity.setModelName(request.modelName());
        entity.setCitationsJson(request.citationsJson());
        entity.setToolCallsJson(request.toolCallsJson());
        entity.setTokensUsed(request.tokensUsed());
        entity.setCreatedAt(LocalDateTime.now());
        entity = messageRepo.save(entity);

        // 更新对话的 updated_at 和 provider
        conversationRepo.findById(conversationId).ifPresent(conv -> {
            conv.setUpdatedAt(LocalDateTime.now());
            if (request.provider() != null) {
                conv.setProvider(request.provider());
            }
            conversationRepo.save(conv);
        });

        return toMessageDto(entity);
    }

    /** 更新对话标题 */
    public ChatConversationDto updateConversation(Long id, ChatUpdateRequest request) {
        ChatConversationEntity entity = conversationRepo.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("对话不存在: " + id));
        if (request.title() != null) {
            entity.setTitle(request.title());
        }
        entity.setUpdatedAt(LocalDateTime.now());
        entity = conversationRepo.save(entity);
        return toConversationDto(entity);
    }

    /** 删除对话（级联删除消息） */
    public void deleteConversation(Long id) {
        messageRepo.deleteByConversationId(id);
        conversationRepo.deleteById(id);
    }

    private void updateConversationTimestamp(Long conversationId) {
        conversationRepo.findById(conversationId).ifPresent(conv -> {
            conv.setUpdatedAt(LocalDateTime.now());
            conversationRepo.save(conv);
        });
    }

    private ChatConversationDto toConversationDto(ChatConversationEntity e) {
        return new ChatConversationDto(e.getId(), e.getUserId(), e.getTitle(), e.getProvider(),
                e.getCreatedAt(), e.getUpdatedAt());
    }

    private ChatMessageDto toMessageDto(ChatMessageEntity e) {
        return new ChatMessageDto(e.getId(), e.getConversationId(), e.getRole(), e.getContent(),
                e.getProvider(), e.getModelName(), e.getCitationsJson(), e.getToolCallsJson(),
                e.getTokensUsed(), e.getCreatedAt());
    }
}
