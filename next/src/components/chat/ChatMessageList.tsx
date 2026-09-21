'use client';

/**
 * @file ChatMessageList — 消息列表组件，渲染用户和 AI 消息。
 * AI 消息支持 Markdown 渲染和引用来源展示。
 * 流式輸出時顯示思考動畫 + 工具調用實時狀態。
 */

import { Wrench, Loader2, CheckCircle2, XCircle, ExternalLink, Brain, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatMessage as ChatMessageType, Citation } from '@/lib/api/chat';

interface ChatMessageListProps {
  messages: ChatMessageType[];
  streamingContent: string;
  activeToolCalls: { tool: string; status: 'running' | 'done' | 'error' }[];
  thinkingMessage?: string;
}

/** 解析 citations JSON */
function parseCitations(json: string | null): Citation[] {
  if (!json) return [];
  try {
    return JSON.parse(json);
  } catch {
    return [];
  }
}

/** 渲染引用来源 */
function CitationsDisplay({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-2 pt-2 border-t border-border/50">
      <p className="text-xs text-muted mb-1">📎 引用来源：</p>
      <div className="space-y-1">
        {citations.map((cite, i) => (
          <div key={i} className="text-xs text-slate-400">
            <span className="text-accent/70">[{i + 1}]</span>{' '}
            <span className="text-slate-300">{cite.source}</span>
            {cite.title && <span>: {cite.title}</span>}
            {cite.url && (
              <a
                href={cite.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 ml-1 text-accent hover:underline"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
            {cite.date && <span className="text-muted"> ({cite.date})</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

/** 工具名稱中文映射 */
const TOOL_NAME_MAP: Record<string, string> = {
  open_web_search: '全網資訊檢索',
  exa_search: '深度語義搜索',
  baidu_search: '百度中文搜索',
  grep_app_search: '開源代碼搜索',
  context7_search: '文檔搜索',
  local_market_data: '本地市場數據',
  ftshare_mcp: 'FTShare 金融數據',
  a_share_mcp: 'A股歷史數據',
};

/** 渲染思考中動畫 */
function ThinkingIndicator({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-accent/80 px-2 py-1.5 rounded bg-accent/5 mb-2">
      <div className="relative flex items-center justify-center w-4 h-4">
        <Brain className="w-4 h-4 animate-pulse" />
        <Sparkles className="absolute w-2 h-2 text-accent animate-ping" style={{ top: -2, right: -2 }} />
      </div>
      <span className="animate-pulse">{message}</span>
      <div className="flex gap-0.5 ml-auto">
        <span className="w-1 h-1 rounded-full bg-accent/60 animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-1 h-1 rounded-full bg-accent/60 animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-1 h-1 rounded-full bg-accent/60 animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  );
}

/** 渲染工具调用状态 */
function ToolCallStatus({ toolCalls }: { toolCalls: { tool: string; status: 'running' | 'done' | 'error' }[] }) {
  if (toolCalls.length === 0) return null;
  return (
    <div className="mb-2 space-y-1">
      {toolCalls.map((tc, i) => {
        const displayName = TOOL_NAME_MAP[tc.tool] || tc.tool;
        return (
          <div
            key={i}
            className={cn(
              'flex items-center gap-1.5 text-xs px-2 py-1 rounded transition-colors',
              tc.status === 'running' && 'bg-blue-500/10 text-blue-400',
              tc.status === 'done' && 'bg-green-500/10 text-green-400',
              tc.status === 'error' && 'bg-red-500/10 text-red-400'
            )}
          >
            <Wrench className="w-3 h-3 flex-shrink-0" />
            <span className="truncate">{displayName}</span>
            {tc.status === 'running' && (
              <span className="flex items-center gap-1 ml-auto text-blue-400/70">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span className="text-[10px]">查詢中</span>
              </span>
            )}
            {tc.status === 'done' && <CheckCircle2 className="w-3 h-3 ml-auto flex-shrink-0" />}
            {tc.status === 'error' && <XCircle className="w-3 h-3 ml-auto flex-shrink-0" />}
          </div>
        );
      })}
    </div>
  );
}

/** 简易 Markdown 渲染（表格 + 代码块 + 粗体 + 标题） */
function renderMarkdown(text: string): React.ReactNode {
  // 按行分割，处理表格、代码块、标题等
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeContent = '';
  let inTable = false;
  let tableRows: string[][] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // 代码块
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre key={`code-${i}`} className="bg-bg text-slate-300 p-2 rounded text-xs overflow-x-auto my-1">
            <code>{codeContent}</code>
          </pre>
        );
        codeContent = '';
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }
    if (inCodeBlock) {
      codeContent += line + '\n';
      continue;
    }

    // 表格
    if (line.includes('|') && line.trim().startsWith('|')) {
      const cells = line.split('|').map(c => c.trim()).filter(c => c !== '');
      // 分隔行（|---|---|）
      if (cells.every(c => /^[-:]+$/.test(c))) {
        inTable = true;
        continue;
      }
      if (!inTable) inTable = true;
      tableRows.push(cells);
      // 检查下一行是否还是表格
      const nextLine = lines[i + 1];
      if (!nextLine || !nextLine.includes('|') || !nextLine.trim().startsWith('|')) {
        // 表格结束
        if (tableRows.length > 0) {
          elements.push(
            <table key={`table-${i}`} className="w-full text-xs border-collapse my-1">
              <thead>
                <tr>
                  {tableRows[0].map((cell, ci) => (
                    <th key={ci} className="border border-border px-2 py-1 text-slate-200 text-left">
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.slice(1).map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td key={ci} className="border border-border px-2 py-1 text-slate-400">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }
        tableRows = [];
        inTable = false;
      }
      continue;
    }
    if (inTable && tableRows.length > 0) {
      elements.push(
        <table key={`table-${i}`} className="w-full text-xs border-collapse my-1">
          <tbody>
            {tableRows.map((row, ri) => (
              <tr key={ri}>
                {row.map((cell, ci) => (
                  <td key={ci} className="border border-border px-2 py-1 text-slate-400">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
      tableRows = [];
      inTable = false;
    }

    // 标题
    if (line.startsWith('### ')) {
      elements.push(<h4 key={`h4-${i}`} className="text-sm font-semibold text-slate-200 mt-2 mb-1">{line.slice(4)}</h4>);
      continue;
    }
    if (line.startsWith('## ')) {
      elements.push(<h3 key={`h3-${i}`} className="text-sm font-bold text-slate-100 mt-2 mb-1">{line.slice(3)}</h3>);
      continue;
    }
    if (line.startsWith('# ')) {
      elements.push(<h2 key={`h2-${i}`} className="text-base font-bold text-slate-100 mt-2 mb-1">{line.slice(2)}</h2>);
      continue;
    }

    // 列表
    if (line.startsWith('- ') || line.startsWith('* ')) {
      elements.push(
        <div key={`li-${i}`} className="text-xs text-slate-300 pl-3">
          • {renderInline(line.slice(2))}
        </div>
      );
      continue;
    }

    // 空行
    if (line.trim() === '') {
      elements.push(<div key={`br-${i}`} className="h-2" />);
      continue;
    }

    // 工具调用内联标记 [[TOOL:工具名:状态]]
    const toolMatch = line.match(/^\[\[TOOL:(.+):(running|done|error)\]\]$/);
    if (toolMatch) {
      const [, toolName, status] = toolMatch;
      const displayName = TOOL_NAME_MAP[toolName] || toolName;
      elements.push(
        <div
          key={`tool-${i}`}
          className={cn(
            'flex items-center gap-1.5 text-xs px-2 py-1 rounded my-1 transition-colors',
            status === 'running' && 'bg-blue-500/10 text-blue-400',
            status === 'done' && 'bg-green-500/10 text-green-400',
            status === 'error' && 'bg-red-500/10 text-red-400'
          )}
        >
          <Wrench className="w-3 h-3 flex-shrink-0" />
          <span className="truncate">{displayName}</span>
          {status === 'running' && (
            <span className="flex items-center gap-1 ml-auto text-blue-400/70">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span className="text-[10px]">查詢中</span>
            </span>
          )}
          {status === 'done' && <CheckCircle2 className="w-3 h-3 ml-auto flex-shrink-0" />}
          {status === 'error' && <XCircle className="w-3 h-3 ml-auto flex-shrink-0" />}
        </div>
      );
      continue;
    }

    // 普通段落
    elements.push(
      <p key={`p-${i}`} className="text-xs text-slate-300 leading-relaxed">
        {renderInline(line)}
      </p>
    );
  }

  // 处理未关闭的代码块
  if (inCodeBlock && codeContent) {
    elements.push(
      <pre key="code-final" className="bg-bg text-slate-300 p-2 rounded text-xs overflow-x-auto my-1">
        <code>{codeContent}</code>
      </pre>
    );
  }

  return elements;
}

/** 渲染行内格式（粗体、链接） */
function renderInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining) {
    // 粗体 **text**
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    // 链接 [text](url)
    const linkMatch = remaining.match(/\[([^\]]+)\]\(([^)]+)\)/);

    if (boldMatch && (!linkMatch || boldMatch.index! < linkMatch.index!)) {
      const before = remaining.slice(0, boldMatch.index);
      if (before) parts.push(<span key={key++}>{before}</span>);
      parts.push(<strong key={key++} className="text-slate-100 font-semibold">{boldMatch[1]}</strong>);
      remaining = remaining.slice(boldMatch.index! + boldMatch[0].length);
    } else if (linkMatch) {
      const before = remaining.slice(0, linkMatch.index);
      if (before) parts.push(<span key={key++}>{before}</span>);
      parts.push(
        <a key={key++} href={linkMatch[2]} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
          {linkMatch[1]}
        </a>
      );
      remaining = remaining.slice(linkMatch.index! + linkMatch[0].length);
    } else {
      parts.push(<span key={key++}>{remaining}</span>);
      break;
    }
  }

  return parts;
}

/** 流式展示時過濾內聯工具標記 [[TOOL:...]] — 工具狀態由 ToolCallStatus 統一展示，避免文字上下重複顯示（歷史消息仍保留內聯標記便於回看）*/
function stripToolMarkers(text: string): string {
  return text.replace(/\n?\[\[TOOL:[^\]]+\]\]\n?/g, '');
}

export function ChatMessageList({ messages, streamingContent, activeToolCalls, thinkingMessage }: ChatMessageListProps) {
  return (
    <>
      {messages.map(msg => {
        const isUser = msg.role === 'user';
        const citations = parseCitations(msg.citationsJson);
        // ChatGPT 風格：用戶消息右對齊灰色氣泡；AI 消息左對齊無氣泡全寬排版
        // 響應式：移動端氣泡更寬（85%）、桌面端適中（70%），間距與字號分級適配
        return (
          <div key={msg.id} className={cn('flex w-full mb-5 last:mb-2', isUser ? 'justify-end' : 'justify-start')}>
            {isUser ? (
              <div className="max-w-[85%] sm:max-w-[75%] md:max-w-[70%] rounded-3xl rounded-br-lg bg-[#323232] px-4 py-2.5 shadow-sm">
                <p className="text-sm leading-relaxed text-slate-50 whitespace-pre-wrap break-words">{msg.content}</p>
              </div>
            ) : (
              <div className="w-full">
                <div className="prose prose-sm prose-invert max-w-none text-slate-100
                  prose-p:leading-relaxed prose-p:my-2 prose-headings:mb-2 prose-headings:mt-3
                  prose-pre:bg-[#0d0d0d] prose-pre:border prose-pre:border-white/10 prose-pre:rounded-xl
                  prose-code:text-[13px] prose-code:before:content-none prose-code:after:content-none
                  prose-li:my-0.5 prose-table:text-[13px]">
                  {renderMarkdown(msg.content)}
                </div>
                <CitationsDisplay citations={citations} />
              </div>
            )}
          </div>
        );
      })}

      {/* 流式輸出中的 AI 回覆 + 打字機光標（ChatGPT 風格：無氣泡全寬排版）*/}
      {(streamingContent || activeToolCalls.length > 0 || thinkingMessage) && (
        <div className="flex w-full justify-start mb-5">
          <div className="w-full">
            {thinkingMessage && (
              <ThinkingIndicator message={thinkingMessage} />
            )}
            {/* 工具調用狀態統一在內容上方展示；流式文本中的內聯標記已過濾，不再重複 */}
            <ToolCallStatus toolCalls={activeToolCalls} />
            {streamingContent && (
              <div className="prose prose-sm prose-invert max-w-none text-slate-100
                prose-p:leading-relaxed prose-p:my-2 prose-headings:mb-2 prose-headings:mt-3
                prose-pre:bg-[#0d0d0d] prose-pre:border prose-pre:border-white/10 prose-pre:rounded-xl
                prose-code:text-[13px] prose-code:before:content-none prose-code:after:content-none
                prose-li:my-0.5 prose-table:text-[13px]">
                {renderMarkdown(stripToolMarkers(streamingContent))}
                {/* 打字機閃爍光標 — 流式輸出進行中時顯示 */}
                <span
                  className="inline-block w-2 h-4 bg-slate-100 ml-0.5 align-text-bottom animate-pulse rounded-sm"
                  style={{ animationDuration: '1s' }}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
