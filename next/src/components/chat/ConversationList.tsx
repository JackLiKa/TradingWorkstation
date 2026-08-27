'use client';

/**
 * @file ConversationList — 歷史對話列表組件。
 *
 * 每條對話顯示：
 * - 標題（截斷 + hover tooltip 顯示完整標題）
 * - 相對時間（「3 分鐘前」「2 小時前」「昨天」「3 天前」）
 * - 供應商標籤（如 GLM-5.2 / DeepSeek）
 * - 消息數（如有）
 */

import { Trash2, MessageSquare, Clock, Cpu, MessageCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatConversation } from '@/lib/api/chat';

interface ConversationListProps {
  conversations: ChatConversation[];
  currentId?: number;
  onSelect: (conv: ChatConversation) => void;
  onDelete: (id: number) => void;
}

/** 供應商顯示名稱映射（簡短版） */
const PROVIDER_LABELS: Record<string, string> = {
  'deepseek-pro': 'DeepSeek Pro',
  'deepseek-flash': 'DeepSeek Flash',
  'glm-5.2': 'GLM-5.2',
  'glm-flash': 'GLM-4 Flash',
  'qwen': 'Qwen3.6',
  'qoder': 'Qoder',
  'devin': 'Devin',
  'ox-alpha': 'OX-Alpha',
};

/** 格式化相對時間 */
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return '剛剛';
  if (diffMin < 60) return `${diffMin} 分鐘前`;
  if (diffHour < 24) return `${diffHour} 小時前`;
  if (diffDay === 1) return '昨天';
  if (diffDay < 7) return `${diffDay} 天前`;
  // 超過 7 天顯示日期
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

/** 格式化完整時間（hover tooltip 用） */
function formatFullTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function ConversationList({ conversations, currentId, onSelect, onDelete }: ConversationListProps) {
  if (conversations.length === 0) {
    return (
      <div className="text-center text-xs text-muted py-8">
        暫無歷史對話
      </div>
    );
  }

  return (
    <div className="space-y-1 px-2 pb-2">
      {conversations.map(conv => {
        const providerLabel = conv.provider ? PROVIDER_LABELS[conv.provider] || conv.provider : null;
        const isActive = currentId === conv.id;

        return (
          <div
            key={conv.id}
            className={cn(
              'group flex items-start gap-2 px-2 py-2 rounded-md cursor-pointer transition-colors',
              isActive
                ? 'bg-accent/10 text-accent'
                : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
            )}
            onClick={() => onSelect(conv)}
            title={conv.title}
          >
            <MessageSquare className={cn('w-3.5 h-3.5 flex-shrink-0 mt-0.5', isActive ? 'text-accent' : 'text-muted')} />

            <div className="flex-1 min-w-0">
              {/* 標題 */}
              <div className="text-xs font-medium truncate text-slate-200">
                {conv.title || '未命名對話'}
              </div>

              {/* 時間 + 供應商 */}
              <div className="flex items-center gap-2 mt-1 text-[10px] text-muted">
                <span className="flex items-center gap-0.5" title={formatFullTime(conv.updatedAt)}>
                  <Clock className="w-2.5 h-2.5" />
                  {formatRelativeTime(conv.updatedAt)}
                </span>
                {providerLabel && (
                  <span className="flex items-center gap-0.5 text-accent/60">
                    <Cpu className="w-2.5 h-2.5" />
                    {providerLabel}
                  </span>
                )}
              </div>
            </div>

            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 text-muted hover:text-red-400 transition-opacity flex-shrink-0 mt-0.5"
              title="刪除對話"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
