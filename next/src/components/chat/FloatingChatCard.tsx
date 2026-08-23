'use client';

/**
 * @file FloatingChatCard — 悬浮 AI 聊天卡片组件。
 *
 * 功能：
 * - 点击悬浮按钮展开/收起聊天面板
 * - 对话列表（历史对话切换 + 新建对话）
 * - 消息列表（支持 Markdown 渲染 + 引用来源展示）
 * - 输入框 + 模型选择器
 * - SSE 流式接收 AI 回复
 * - 工具调用状态实时展示
 * - 对话持久化（Java 后端 MySQL）
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageCircle, X, Plus, Send, Trash2, Loader2, ChevronLeft, Bot, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import { chatApi, type ChatConversation, type ChatMessage as ChatMessageType, type ChatProvider, type Citation, type SSEEvent } from '@/lib/api/chat';
import { ChatMessageList } from './ChatMessageList';
import { ChatInput } from './ChatInput';
import { ConversationList } from './ConversationList';

export function FloatingChatCard() {
  const [isOpen, setIsOpen] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [currentConversation, setCurrentConversation] = useState<ChatConversation | null>(null);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [providers, setProviders] = useState<ChatProvider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [activeToolCalls, setActiveToolCalls] = useState<{ tool: string; status: 'running' | 'done' | 'error' }[]>([]);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 加载供应商列表
  useEffect(() => {
    if (isOpen && providers.length === 0) {
      chatApi.getChatProviders().then(setProviders).catch(() => {});
    }
  }, [isOpen, providers.length]);

  // 加载对话列表
  const loadConversations = useCallback(async () => {
    try {
      const list = await chatApi.listConversations();
      setConversations(list);
    } catch (e) {
      console.error('加载对话列表失败:', e);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadConversations();
    }
  }, [isOpen, loadConversations]);

  // 加载对话消息
  const loadMessages = useCallback(async (conversationId: number) => {
    try {
      const msgs = await chatApi.getMessages(conversationId);
      setMessages(msgs);
    } catch (e) {
      console.error('加载消息失败:', e);
      setMessages([]);
    }
  }, []);

  // 切换对话
  const switchConversation = useCallback((conv: ChatConversation) => {
    setCurrentConversation(conv);
    setShowSidebar(false);
    loadMessages(conv.id);
  }, [loadMessages]);

  // 新建对话
  const newConversation = useCallback(async () => {
    try {
      const conv = await chatApi.createConversation('新对话', selectedProvider || undefined);
      setCurrentConversation(conv);
      setMessages([]);
      setShowSidebar(false);
      await loadConversations();
    } catch (e) {
      setError('创建对话失败: ' + (e as Error).message);
    }
  }, [selectedProvider, loadConversations]);

  // 删除对话
  const deleteConversation = useCallback(async (id: number) => {
    try {
      await chatApi.deleteConversation(id);
      if (currentConversation?.id === id) {
        setCurrentConversation(null);
        setMessages([]);
      }
      await loadConversations();
    } catch (e) {
      setError('删除对话失败: ' + (e as Error).message);
    }
  }, [currentConversation, loadConversations]);

  // 发送消息
  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isStreaming) return;

    // 如果没有当前对话，先创建一个
    let conv = currentConversation;
    if (!conv) {
      try {
        conv = await chatApi.createConversation('新对话', selectedProvider || undefined);
        setCurrentConversation(conv);
        await loadConversations();
      } catch (e) {
        setError('创建对话失败: ' + (e as Error).message);
        return;
      }
    }

    // 保存用户消息到后端
    try {
      const userMsg = await chatApi.saveUserMessage(conv.id, content, selectedProvider || undefined);
      setMessages(prev => [...prev, userMsg]);
    } catch (e) {
      setError('保存消息失败: ' + (e as Error).message);
      return;
    }

    // 开始流式接收
    setIsStreaming(true);
    setStreamingContent('');
    setActiveToolCalls([]);
    setError('');

    // 构建消息历史（含当前消息）
    const history = [...messages, { role: 'user', content }]
      .filter(m => m.content)
      .map(m => ({ role: m.role, content: m.content }));

    let fullContent = '';
    let allCitations: Citation[] = [];
    let provider = '';
    let model = '';
    let toolCallsLog: { tool: string; arguments: string; success: boolean; content_preview: string }[] = [];
    let tokens = 0;

    try {
      const generator = chatApi.chatStream(history, selectedProvider || undefined);

      for await (const event of generator) {
        switch (event.type) {
          case 'tool_start':
            setActiveToolCalls(prev => [...prev, { tool: event.tool, status: 'running' }]);
            break;
          case 'tool_end':
            setActiveToolCalls(prev =>
              prev.map(tc =>
                tc.tool === event.tool && tc.status === 'running'
                  ? { tool: event.tool, status: event.success ? 'done' : 'error' }
                  : tc
              )
            );
            if (event.citations) {
              allCitations = [...allCitations, ...event.citations];
            }
            break;
          case 'content':
            fullContent += event.text;
            setStreamingContent(fullContent);
            break;
          case 'done':
            provider = event.provider;
            model = event.model;
            allCitations = [...allCitations, ...event.citations];
            toolCallsLog = event.tool_calls_log;
            tokens = event.tokens;
            break;
          case 'error':
            setError(event.message);
            break;
        }
      }

      // 保存 AI 回复到后端
      if (fullContent) {
        try {
          const assistantMsg = await chatApi.saveAssistantReply(conv.id, {
            content: fullContent,
            provider,
            modelName: model,
            citationsJson: JSON.stringify(allCitations),
            toolCallsJson: JSON.stringify(toolCallsLog),
            tokensUsed: tokens,
          });
          setMessages(prev => [...prev, assistantMsg]);
        } catch (e) {
          console.error('保存 AI 回复失败:', e);
        }
      }

      // 刷新对话列表（标题可能已更新）
      await loadConversations();
    } catch (e) {
      setError('流式聊天失败: ' + (e as Error).message);
    } finally {
      setIsStreaming(false);
      setStreamingContent('');
      setActiveToolCalls([]);
    }
  }, [currentConversation, isStreaming, messages, selectedProvider, loadConversations]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center justify-center w-14 h-14 rounded-full bg-accent text-white shadow-lg hover:bg-accent/90 transition-all hover:scale-105"
        title="AI 投研助手"
      >
        <Bot className="w-6 h-6" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex">
      {/* 侧边栏：对话列表 */}
      {showSidebar && (
        <div className="mr-2 w-64 h-[600px] bg-bg-panel border border-border rounded-lg shadow-xl flex flex-col">
          <div className="flex items-center justify-between p-3 border-b border-border">
            <span className="text-sm font-semibold text-slate-200">对话历史</span>
            <button
              onClick={() => setShowSidebar(false)}
              className="text-muted hover:text-slate-200"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          </div>
          <div className="p-2">
            <button
              onClick={newConversation}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
            >
              <Plus className="w-4 h-4" />
              新建对话
            </button>
          </div>
          <div className="flex-1 overflow-auto">
            <ConversationList
              conversations={conversations}
              currentId={currentConversation?.id}
              onSelect={switchConversation}
              onDelete={deleteConversation}
            />
          </div>
        </div>
      )}

      {/* 主聊天面板 */}
      <div className="w-[440px] h-[600px] bg-bg-panel border border-border rounded-lg shadow-xl flex flex-col">
        {/* 标题栏 */}
        <div className="flex items-center justify-between p-3 border-b border-border">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="text-muted hover:text-slate-200"
              title="对话历史"
            >
              <MessageCircle className="w-4 h-4" />
            </button>
            <span className="text-sm font-semibold text-slate-200">AI 投研助手</span>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="text-muted hover:text-slate-200"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-auto p-3 space-y-3">
          {messages.length === 0 && !streamingContent && !isStreaming && (
            <div className="flex flex-col items-center justify-center h-full text-center text-muted">
              <Bot className="w-12 h-12 mb-3 opacity-50" />
              <p className="text-sm">我是你的量化投研助手</p>
              <p className="text-xs mt-1">可以问我市场行情、财经新闻、策略分析等</p>
              <p className="text-xs mt-2 text-accent/70">所有回答基于真实数据，引用可追溯</p>
            </div>
          )}
          <ChatMessageList
            messages={messages}
            streamingContent={streamingContent}
            activeToolCalls={activeToolCalls}
          />
          {error && (
            <div className="text-xs text-red-400 bg-red-400/10 rounded p-2">
              {error}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区 */}
        <ChatInput
          onSend={sendMessage}
          disabled={isStreaming}
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />
      </div>
    </div>
  );
}
