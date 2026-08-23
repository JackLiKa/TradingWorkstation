/**
 * @file AI 聊天 API 客戶�?�?對話 CRUD �?Java 後端，流式聊天走 Agent SSE�? */

import { apiPost, apiFetch, apiDelete, apiPatch } from './client';

// ===== 類型定義 =====

export interface ChatConversation {
  id: number;
  userId: string;
  title: string;
  provider: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ChatMessage {
  id: number;
  conversationId: number;
  role: 'user' | 'assistant';
  content: string;
  provider: string | null;
  modelName: string | null;
  citationsJson: string | null;
  toolCallsJson: string | null;
  tokensUsed: number | null;
  createdAt: string;
}

export interface ChatProvider {
  provider: string;
  display_name: string;
  model_id: string;
  is_free: boolean;
  available: boolean;
  description: string;
}

export interface ChatTool {
  name: string;
  display_name: string;
  description: string;
}

export interface Citation {
  source: string;
  title: string;
  url: string;
  snippet?: string;
  date?: string;
  [key: string]: unknown;
}

export interface ToolCallLog {
  tool: string;
  arguments: string;
  success: boolean;
  content_preview: string;
}

// ===== SSE 事件類型 =====

export interface SSEToolStart {
  type: 'tool_start';
  tool: string;
  arguments: Record<string, unknown>;
}

export interface SSEToolEnd {
  type: 'tool_end';
  tool: string;
  success: boolean;
  citations: Citation[];
  error: string;
}

export interface SSEContent {
  type: 'content';
  text: string;
}

export interface SSEDone {
  type: 'done';
  provider: string;
  model: string;
  citations: Citation[];
  tool_calls_log: ToolCallLog[];
  tokens: number;
}

export interface SSEError {
  type: 'error';
  message: string;
}

export type SSEEvent = SSEToolStart | SSEToolEnd | SSEContent | SSEDone | SSEError;

// ===== Java 後端 API（對�?CRUD�?====

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/TradingWorkstation';
const AGENT_PROXY = `${API_BASE}/agent-api`;
const AGENT_API_KEY = process.env.NEXT_PUBLIC_AGENT_API_KEY || '';

function agentHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (AGENT_API_KEY) headers['X-API-Key'] = AGENT_API_KEY;
  return headers;
}

export const chatApi = {
  // ===== 對話管理（Java 後端�?====

  /** 創建新對�?*/
  createConversation: (title?: string, provider?: string) =>
    apiPost<ChatConversation>('/chat/conversations', { title, provider }),

  /** 列出全部對話 */
  listConversations: () => apiFetch<ChatConversation[]>('/chat/conversations'),

  /** 獲取對話消息列表 */
  getMessages: (conversationId: number) =>
    apiFetch<ChatMessage[]>(`/chat/conversations/${conversationId}/messages`),

  /** 保存用戶消息 */
  saveUserMessage: (conversationId: number, content: string, provider?: string) =>
    apiPost<ChatMessage>(`/chat/conversations/${conversationId}/messages`, { content, provider }),

  /** 保存 AI 回復 */
  saveAssistantReply: (
    conversationId: number,
    data: {
      content: string;
      provider: string;
      modelName: string;
      citationsJson: string;
      toolCallsJson: string;
      tokensUsed: number;
    }
  ) => apiPost<ChatMessage>(`/chat/conversations/${conversationId}/reply`, data),

  /** 更新對話標題 */
  updateConversation: (conversationId: number, title: string) =>
    apiPatch<ChatConversation>(`/chat/conversations/${conversationId}`, { title }),

  /** 刪除對話 */
  deleteConversation: (conversationId: number) =>
    apiDelete<void>(`/chat/conversations/${conversationId}`),

  // ===== Agent 服務 API（聊�?+ 工具�?====

  /** 獲取可用 LLM 供應�?*/
  getChatProviders: async (): Promise<ChatProvider[]> => {
    const res = await fetch(`${AGENT_PROXY}/chat/providers`, { headers: agentHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.providers;
  },

  /** 獲取可用工具列表 */
  getChatTools: async (): Promise<ChatTool[]> => {
    const res = await fetch(`${AGENT_PROXY}/chat/tools`, { headers: agentHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.tools;
  },

  /**
   * 流式聊天 �?返回 AsyncGenerator，yield SSE 事件�?   * 使用 fetch + ReadableStream 解析 SSE（而非 EventSource，因為需�?POST）�?   */
  chatStream: async function* (
    messages: { role: string; content: string }[],
    provider?: string
  ): AsyncGenerator<SSEEvent> {
    const res = await fetch(`${AGENT_PROXY}/chat/stream`, {
      method: 'POST',
      headers: agentHeaders(),
      body: JSON.stringify({ messages, provider }),
    });

    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE 格式：data: {...}\n\n
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 保留最後一個不完整的行

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.slice(6);
          try {
            const event = JSON.parse(jsonStr) as SSEEvent;
            yield event;
          } catch {
            // 忽略解析失敗的行
          }
        }
      }
    }

    // 處理緩衝區剩餘數據
    if (buffer.trim().startsWith('data: ')) {
      try {
        const event = JSON.parse(buffer.trim().slice(6)) as SSEEvent;
        yield event;
      } catch {
        // 忽略
      }
    }
  },
};

