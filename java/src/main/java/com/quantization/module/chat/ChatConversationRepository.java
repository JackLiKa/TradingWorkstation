package com.quantization.module.chat;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 聊天对话 Repository — 提供对话的 CRUD 和按用户查询。
 */
@Repository
public interface ChatConversationRepository extends JpaRepository<ChatConversationEntity, Long> {

    /** 按用户查询全部对话，按更新时间倒序 */
    List<ChatConversationEntity> findByUserIdOrderByUpdatedAtDesc(String userId);
}
