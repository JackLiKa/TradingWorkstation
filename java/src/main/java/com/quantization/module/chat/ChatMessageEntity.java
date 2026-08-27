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
 * AI 聊天消息实体 — 存储对话中的每条消息（用户消息 + AI 回复）。
 * citations_json 存储引用来源（新闻、行情数据、搜索结果的出处）。
 * tool_calls_json 存储 AI 调用的工具链（工具名、参数、结果摘要）。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "chat_message")
public class ChatMessageEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    /** 所属对话 ID */
    @Column(name = "conversation_id", nullable = false)
    private Long conversationId;

    /** 消息角色：user / assistant */
    @Column(name = "role", nullable = false, length = 20)
    private String role;

    /** 消息内容（AI 回复可能含 Markdown） */
    @Column(name = "content", columnDefinition = "MEDIUMTEXT")
    private String content;

    /** AI 回复使用的 LLM 供应商 */
    @Column(name = "provider", length = 32)
    private String provider;

    /** AI 回复使用的模型名称 */
    @Column(name = "model_name", length = 64)
    private String modelName;

    /** 引用来源 JSON（新闻标题/日期/URL、行情数据来源、搜索结果片段） */
    @Column(name = "citations_json", columnDefinition = "MEDIUMTEXT")
    private String citationsJson;

    /** 工具调用链 JSON（工具名、参数、结果摘要） */
    @Column(name = "tool_calls_json", columnDefinition = "MEDIUMTEXT")
    private String toolCallsJson;

    /** 本次消息消耗的 token 数 */
    @Column(name = "tokens_used")
    private Integer tokensUsed;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;
}
