'use client';

/**
 * @file FloatingChatCard — 懸浮 AI 聊天卡片組件。
 *
 * 功能：
 * - 點擊懸浮按鈕展開/收起聊天面板
 * - 對話列表（歷史對話切換 + 新建對話）
 * - 消息列表（Markdown 渲染 + 引用來源展示）
 * - 輸入框 + 模型選擇器
 * - SSE 流式接收 AI 回復
 * - 工具調用狀態實時展示
 * - 對話持久化（Java 後端 MySQL）
 * - **可拖拽位置**（左鍵拖拽標題欄）+ **8 方向可調整大小**（拖拽邊框）+ localStorage 持久化
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageCircle, X, Plus, Bot, Move, ChevronLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { chatApi, type ChatConversation, type ChatMessage as ChatMessageType, type ChatProvider, type Citation, type SSEEvent } from '@/lib/api/chat';
import { ChatMessageList } from './ChatMessageList';
import { ChatInput } from './ChatInput';
import { ConversationList } from './ConversationList';

// ===== 位置/大小持久化配置 =====
const STORAGE_KEY = 'chat-card-layout-v2';
const DEFAULT_LAYOUT = {
  left: 0,     // 距離視窗左邊的像素（0 = 由 CSS right:24px 默認定位，首次加載時自動計算）
  top: 0,      // 距離視窗頂部的像素
  width: 440,
  height: 600,
  initialized: false,  // 是否已從默認位置計算過 left/top
};
const MIN_WIDTH = 320;
const MIN_HEIGHT = 400;
const MAX_WIDTH = 900;
const MAX_HEIGHT = 1000;
// resize 把手寬度（像素）— 邊框可拖拽區域
const HANDLE_SIZE = 6;
const CORNER_SIZE = 14;

type ResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';

interface ChatLayout {
  left: number;
  top: number;
  width: number;
  height: number;
  initialized: boolean;
}

function loadLayout(): ChatLayout {
  if (typeof window === 'undefined') return { ...DEFAULT_LAYOUT };
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const p = JSON.parse(saved);
      return {
        left: p.left ?? 0,
        top: p.top ?? 0,
        width: Math.min(Math.max(p.width ?? 440, MIN_WIDTH), MAX_WIDTH),
        height: Math.min(Math.max(p.height ?? 600, MIN_HEIGHT), MAX_HEIGHT),
        initialized: p.initialized ?? false,
      };
    }
  } catch { /* ignore */ }
  return { ...DEFAULT_LAYOUT };
}

function saveLayout(layout: ChatLayout) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
  } catch { /* ignore */ }
}

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
  const [thinkingMessage, setThinkingMessage] = useState('');
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ===== 佈局 + 拖拽狀態 =====
  const [layout, setLayout] = useState<ChatLayout>(DEFAULT_LAYOUT);
  const [dragMode, setDragMode] = useState<'move' | ResizeDir | null>(null);
  // 使用 null 表示無操作 — 這是關鍵修復（舊代碼用 'move' 作為默認值導致松開鼠標後仍繼續拖拽）
  const dragState = useRef<{
    mode: 'move' | ResizeDir | null;
    startX: number;
    startY: number;
    startLayout: ChatLayout;
  }>({ mode: null, startX: 0, startY: 0, startLayout: DEFAULT_LAYOUT });

  // 加載保存的佈局（首次打開時計算默認位置）
  useEffect(() => {
    const loaded = loadLayout();
    if (!loaded.initialized) {
      // 首次：放在右下角（距離右邊 24px，距離底部 24px）
      loaded.left = window.innerWidth - loaded.width - 24;
      loaded.top = window.innerHeight - loaded.height - 24;
      loaded.initialized = true;
      saveLayout(loaded);
    }
    setLayout(loaded);
  }, []);

  // ===== 移動端檢測（屏幕寬度 ≤ 768px 時使用全屏覆蓋模式）=====
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth <= 768);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // ===== 拖拽位置（標題欄左鍵）=====
  const handleDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    // 不在按鈕上才拖拽
    if ((e.target as HTMLElement).closest('button')) return;
    // 只響應左鍵
    if ('button' in e && e.button !== 0) return;
    e.preventDefault();
    const point = 'touches' in e ? e.touches[0] : e;
    dragState.current = {
      mode: 'move',
      startX: point.clientX,
      startY: point.clientY,
      startLayout: layout,
    };
    setDragMode('move');
  }, [layout]);

  // ===== 調整大小（8 方向邊框拖拽）=====
  const handleResizeStart = useCallback((e: React.MouseEvent | React.TouchEvent, dir: ResizeDir) => {
    // 只響應左鍵
    if ('button' in e && e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const point = 'touches' in e ? e.touches[0] : e;
    dragState.current = {
      mode: dir,
      startX: point.clientX,
      startY: point.clientY,
      startLayout: layout,
    };
    setDragMode(dir);
  }, [layout]);

  // 全局鼠標/觸摸移動/釋放
  useEffect(() => {
    if (!isOpen) return;

    const handleMove = (clientX: number, clientY: number) => {
      const ds = dragState.current;
      // 關鍵修復：mode 為 null 時不處理（舊代碼 mode 默認 'move' 導致松開後仍拖拽）
      if (!ds.mode) return;

      const start = ds.startLayout;
      const dx = clientX - ds.startX;
      const dy = clientY - ds.startY;

      if (ds.mode === 'move') {
        // left/top 定位，直接加偏移
        let newLeft = start.left + dx;
        let newTop = start.top + dy;
        // 邊界限制：至少保留部分在視窗內
        newLeft = Math.min(Math.max(newLeft, -start.width + 100), window.innerWidth - 100);
        newTop = Math.min(Math.max(newTop, 0), window.innerHeight - 60);
        setLayout(prev => ({ ...prev, left: newLeft, top: newTop }));
        return;
      }

      // ===== 8 方向 resize（left/top 定位，數學直觀）=====
      let { left, top, width, height } = start;

      // 東方向（e/se/ne）：拖右邊框向右 → 寬度增加，左邊不動
      if (ds.mode.includes('e')) {
        width = Math.min(Math.max(start.width + dx, MIN_WIDTH), MAX_WIDTH);
      }
      // 西方向（w/sw/nw）：拖左邊框向左 → 寬度增加，右邊不動 → left 隨之減少
      if (ds.mode.includes('w')) {
        width = Math.min(Math.max(start.width - dx, MIN_WIDTH), MAX_WIDTH);
        left = start.left + (start.width - width);
      }
      // 南方向（s/se/sw）：拖下邊框向下 → 高度增加，上邊不動
      if (ds.mode.includes('s')) {
        height = Math.min(Math.max(start.height + dy, MIN_HEIGHT), MAX_HEIGHT);
      }
      // 北方向（n/ne/nw）：拖上邊框向上 → 高度增加，下邊不動 → top 隨之減少
      if (ds.mode.includes('n')) {
        height = Math.min(Math.max(start.height - dy, MIN_HEIGHT), MAX_HEIGHT);
        top = start.top + (start.height - height);
      }

      // 邊界限制：確保卡片不超出視窗
      left = Math.min(Math.max(left, 0), window.innerWidth - width);
      top = Math.min(Math.max(top, 0), window.innerHeight - height);

      setLayout(prev => ({ ...prev, left, top, width, height }));
    };

    const handleMouseMove = (e: MouseEvent) => handleMove(e.clientX, e.clientY);

    const handleTouchMove = (e: TouchEvent) => {
      if (!dragState.current.mode) return;
      e.preventDefault();
      const t = e.touches[0];
      handleMove(t.clientX, t.clientY);
    };

    const handleEnd = () => {
      // 關鍵修復：mode 設為 null（不是 'move'），這樣鬆開鼠標後移動鼠標不會繼續拖拽
      if (dragState.current.mode) {
        dragState.current.mode = null;
        setDragMode(null);
        setLayout(prev => {
          saveLayout(prev);
          return prev;
        });
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleEnd);
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('touchend', handleEnd);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleEnd);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleEnd);
    };
  }, [isOpen]);

  // 加載供應商列表
  useEffect(() => {
    if (isOpen && providers.length === 0) {
      chatApi.getChatProviders().then(setProviders).catch(() => {});
    }
  }, [isOpen, providers.length]);

  const loadConversations = useCallback(async () => {
    try {
      const list = await chatApi.listConversations();
      setConversations(list);
    } catch (e) {
      console.error('加載對話列表失敗:', e);
    }
  }, []);

  useEffect(() => {
    if (isOpen) loadConversations();
  }, [isOpen, loadConversations]);

  const loadMessages = useCallback(async (conversationId: number) => {
    try {
      const msgs = await chatApi.getMessages(conversationId);
      setMessages(msgs);
    } catch (e) {
      console.error('加載消息失敗:', e);
      setMessages([]);
    }
  }, []);

  const switchConversation = useCallback((conv: ChatConversation) => {
    setCurrentConversation(conv);
    setShowSidebar(false);
    loadMessages(conv.id);
  }, [loadMessages]);

  const newConversation = useCallback(async () => {
    try {
      const conv = await chatApi.createConversation('新對話', selectedProvider || undefined);
      setCurrentConversation(conv);
      setMessages([]);
      setShowSidebar(false);
      await loadConversations();
    } catch (e) {
      setError('創建對話失敗: ' + (e as Error).message);
    }
  }, [selectedProvider, loadConversations]);

  const deleteConversation = useCallback(async (id: number) => {
    try {
      await chatApi.deleteConversation(id);
      if (currentConversation?.id === id) {
        setCurrentConversation(null);
        setMessages([]);
      }
      await loadConversations();
    } catch (e) {
      setError('刪除對話失敗: ' + (e as Error).message);
    }
  }, [currentConversation, loadConversations]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isStreaming) return;

    let conv = currentConversation;
    if (!conv) {
      try {
        conv = await chatApi.createConversation('新對話', selectedProvider || undefined);
        setCurrentConversation(conv);
        await loadConversations();
      } catch (e) {
        setError('創建對話失敗: ' + (e as Error).message);
        return;
      }
    }

    try {
      const userMsg = await chatApi.saveUserMessage(conv.id, content, selectedProvider || undefined);
      setMessages(prev => [...prev, userMsg]);
    } catch (e) {
      setError('保存消息失敗: ' + (e as Error).message);
      return;
    }

    setIsStreaming(true);
    setStreamingContent('');
    setActiveToolCalls([]);
    setThinkingMessage('AI 正在分析您的問題...');
    setError('');

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
          case 'thinking':
            setThinkingMessage(event.message);
            break;
          case 'tool_start':
            setThinkingMessage('');
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
            break;
          case 'content':
            setThinkingMessage('');
            fullContent += event.text;
            setStreamingContent(fullContent);
            break;
          case 'done':
            provider = event.provider;
            model = event.model;
            allCitations = event.citations || [];
            toolCallsLog = event.tool_calls_log || [];
            tokens = event.tokens;
            break;
          case 'error':
            setError(event.message);
            break;
        }
      }

      if (fullContent) {
        try {
          const citationsJson = JSON.stringify(allCitations);
          const assistantMsg = await chatApi.saveAssistantReply(conv.id, {
            content: fullContent,
            provider,
            modelName: model,
            citationsJson,
            toolCallsJson: JSON.stringify(toolCallsLog),
            tokensUsed: tokens,
          });
          setMessages(prev => [...prev, assistantMsg]);
        } catch (e) {
          console.error('保存 AI 回復失敗:', e);
          setMessages(prev => [...prev, {
            id: Date.now(),
            conversationId: conv.id,
            role: 'assistant' as const,
            content: fullContent,
            provider,
            modelName: model,
            citationsJson: JSON.stringify(allCitations),
            toolCallsJson: JSON.stringify(toolCallsLog),
            tokensUsed: tokens,
            createdAt: new Date().toISOString(),
          }]);
          setError('AI 回復已生成但保存失敗（刷新後可能丟失）: ' + (e as Error).message);
        }
      }

      await loadConversations();
    } catch (e) {
      setError('流式聊天失敗: ' + (e as Error).message);
    } finally {
      setIsStreaming(false);
      setStreamingContent('');
      setActiveToolCalls([]);
      setThinkingMessage('');
    }
  }, [currentConversation, isStreaming, messages, selectedProvider, loadConversations]);

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

  // ===== 移動端全屏覆蓋模式（避免固定像素定位導致超出屏幕）=====
  if (isMobile) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col bg-bg-panel">
        {/* 標題欄 */}
        <div className="flex items-center justify-between p-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="text-muted hover:text-slate-200 p-1"
              title="對話歷史"
            >
              <MessageCircle className="w-5 h-5" />
            </button>
            <span className="text-sm font-semibold text-slate-200">AI 投研助手</span>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="text-muted hover:text-slate-200 p-1"
            title="關閉"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 對話歷史側邊欄（移動端展開覆蓋） */}
        {showSidebar && (
          <div className="absolute inset-0 z-10 bg-bg-panel flex flex-col">
            <div className="flex items-center justify-between p-3 border-b border-border shrink-0">
              <span className="text-sm font-semibold text-slate-200">對話歷史</span>
              <button
                onClick={() => setShowSidebar(false)}
                className="text-muted hover:text-slate-200 p-1"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
            </div>
            <div className="p-2 shrink-0">
              <button
                onClick={newConversation}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
              >
                <Plus className="w-4 h-4" />
                新建對話
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

        {/* 消息列表 */}
        <div className="flex-1 overflow-auto p-3 space-y-3 min-h-0">
          {messages.length === 0 && !streamingContent && !isStreaming && (
            <div className="flex flex-col items-center justify-center h-full text-center text-muted">
              <Bot className="w-12 h-12 mb-3 opacity-50" />
              <p className="text-sm">我是你的量化投研助手</p>
              <p className="text-xs mt-1">可以問我市場行情、財經新聞、策略分析等</p>
              <p className="text-xs mt-2 text-accent/70">所有回答基於真實數據，引用可追溯</p>
            </div>
          )}
          <ChatMessageList
            messages={messages}
            streamingContent={streamingContent}
            activeToolCalls={activeToolCalls}
            thinkingMessage={thinkingMessage}
          />
          {error && (
            <div className="text-xs text-red-400 bg-red-400/10 rounded p-2">
              {error}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 輸入區 */}
        <ChatInput
          onSend={sendMessage}
          disabled={isStreaming}
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />
      </div>
    );
  }

  const isInteracting = dragMode !== null;

  // 8 方向 resize 把手配置 — 邊框可拖拽區域
  const resizeHandles: { dir: ResizeDir; style: React.CSSProperties; cursor: string }[] = [
    // 4 條邊
    { dir: 'n',  style: { top: -HANDLE_SIZE/2, left: CORNER_SIZE, right: CORNER_SIZE, height: HANDLE_SIZE }, cursor: 'cursor-n-resize' },
    { dir: 's',  style: { bottom: -HANDLE_SIZE/2, left: CORNER_SIZE, right: CORNER_SIZE, height: HANDLE_SIZE }, cursor: 'cursor-s-resize' },
    { dir: 'e',  style: { right: -HANDLE_SIZE/2, top: CORNER_SIZE, bottom: CORNER_SIZE, width: HANDLE_SIZE }, cursor: 'cursor-e-resize' },
    { dir: 'w',  style: { left: -HANDLE_SIZE/2, top: CORNER_SIZE, bottom: CORNER_SIZE, width: HANDLE_SIZE }, cursor: 'cursor-w-resize' },
    // 4 個角
    { dir: 'ne', style: { top: -CORNER_SIZE/2, right: -CORNER_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE }, cursor: 'cursor-ne-resize' },
    { dir: 'nw', style: { top: -CORNER_SIZE/2, left: -CORNER_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE }, cursor: 'cursor-nw-resize' },
    { dir: 'se', style: { bottom: -CORNER_SIZE/2, right: -CORNER_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE }, cursor: 'cursor-se-resize' },
    { dir: 'sw', style: { bottom: -CORNER_SIZE/2, left: -CORNER_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE }, cursor: 'cursor-sw-resize' },
  ];

  return (
    <div
      className="fixed z-50 flex"
      style={{
        left: `${layout.left}px`,
        top: `${layout.top}px`,
      }}
    >
      {/* 側邊欄：對話列表 */}
      {showSidebar && (
        <div
          className="mr-2 bg-bg-panel border border-border rounded-lg shadow-xl flex flex-col"
          style={{ width: '260px', height: `${layout.height}px` }}
        >
          <div className="flex items-center justify-between p-3 border-b border-border">
            <span className="text-sm font-semibold text-slate-200">對話歷史</span>
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
              新建對話
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
      <div
        className={cn(
          'bg-bg-panel border-2 border-border rounded-lg flex flex-col relative',
          isInteracting ? 'shadow-2xl ring-2 ring-accent/50 border-accent/40' : 'shadow-xl'
        )}
        style={{
          width: `${layout.width}px`,
          height: `${layout.height}px`,
          userSelect: isInteracting ? 'none' : 'auto',
        }}
      >
        {/* 標題欄 — 左鍵拖拽移動位置 */}
        <div
          onMouseDown={handleDragStart}
          onTouchStart={handleDragStart}
          className={cn(
            'flex items-center justify-between p-3 border-b border-border select-none',
            dragMode === 'move' ? 'cursor-grabbing bg-accent/5' : 'cursor-grab'
          )}
          title="拖拽移動位置"
        >
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="text-muted hover:text-slate-200"
              title="對話歷史"
            >
              <MessageCircle className="w-4 h-4" />
            </button>
            <span className="text-sm font-semibold text-slate-200">AI 投研助手</span>
            <Move className="w-3 h-3 text-muted/50" />
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="text-muted hover:text-slate-200"
            title="關閉"
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
              <p className="text-xs mt-1">可以問我市場行情、財經新聞、策略分析等</p>
              <p className="text-xs mt-2 text-accent/70">所有回答基於真實數據，引用可追溯</p>
            </div>
          )}
          <ChatMessageList
            messages={messages}
            streamingContent={streamingContent}
            activeToolCalls={activeToolCalls}
            thinkingMessage={thinkingMessage}
          />
          {error && (
            <div className="text-xs text-red-400 bg-red-400/10 rounded p-2">
              {error}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 輸入區 */}
        <ChatInput
          onSend={sendMessage}
          disabled={isStreaming}
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />

        {/* ===== 8 方向調整大小把手（拖拽邊框）===== */}
        {resizeHandles.map(({ dir, style, cursor }) => (
          <div
            key={dir}
            onMouseDown={(e) => handleResizeStart(e, dir)}
            onTouchStart={(e) => handleResizeStart(e, dir)}
            className={cn(
              'absolute z-20 bg-transparent',
              cursor,
              // hover 時顯示邊框高亮，讓用戶知道可以拖拽
              'hover:bg-accent/20',
              // 拖拽中顯示更強的高亮
              isInteracting && dragMode === dir && 'bg-accent/30',
            )}
            style={style}
          />
        ))}

        {/* 右下角視覺指示器（疊在 se 把手上，pointer-events-none 不影響拖拽） */}
        <div
          className="absolute pointer-events-none flex items-end justify-end"
          style={{ bottom: 0, right: 0, width: CORNER_SIZE, height: CORNER_SIZE }}
        >
          <svg
            className={cn(
              'w-3 h-3 transition-colors',
              dragMode === 'se' ? 'text-accent' : 'text-muted/30'
            )}
            viewBox="0 0 10 10"
            fill="none"
          >
            <path d="M9 1L1 9M9 5L5 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    </div>
  );
}
