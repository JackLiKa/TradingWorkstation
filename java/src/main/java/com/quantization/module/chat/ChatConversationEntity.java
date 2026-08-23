package com.quantization.module.chat;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * AI 聊天对话实体 — 存储用户与 AI 的对话会话元数据。
 * 支持多对话管理、历史对话延续、记忆管理。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "chat_conversation")
public class ChatConversationEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** 用户标识（当前单用户模式，固定为 'default'） */
    @Column(name = "user_id", nullable = false, length = 64)
    private String userId;

    /** 对话标题（默认 '新对话'，可由用户修改或根据首条消息自动生成） */
    @Column(name = "title", nullable = false, length = 200)
    private String title;

    /** 最后使用的 LLM 供应商 */
    @Column(name = "provider", length = 32)
    private String provider;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
