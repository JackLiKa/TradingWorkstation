package com.quantization.module.chat;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 聊天消息 Repository — 提供按对话查询消息列表。
 */
@Repository
public interface ChatMessageRepository extends JpaRepository<ChatMessageEntity, Long> {

    /** 按对话 ID 查询全部消息，按创建时间正序（对话时间线顺序） */
    List<ChatMessageEntity> findByConversationIdOrderByCreatedAtAsc(Long conversationId);

    /** 删除指定对话的全部消息 */
    void deleteByConversationId(Long conversationId);
}
