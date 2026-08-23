'use client';

/**
 * @file ConversationList — 历史对话列表组件。
 */

import { Trash2, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatConversation } from '@/lib/api/chat';

interface ConversationListProps {
  conversations: ChatConversation[];
  currentId?: number;
  onSelect: (conv: ChatConversation) => void;
  onDelete: (id: number) => void;
}

export function ConversationList({ conversations, currentId, onSelect, onDelete }: ConversationListProps) {
  if (conversations.length === 0) {
    return (
      <div className="text-center text-xs text-muted py-8">
        暂无历史对话
      </div>
    );
  }

  return (
    <div className="space-y-1 px-2 pb-2">
      {conversations.map(conv => (
        <div
          key={conv.id}
          className={cn(
            'group flex items-center gap-2 px-2 py-2 rounded-md cursor-pointer transition-colors',
            currentId === conv.id
              ? 'bg-accent/10 text-accent'
              : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
          )}
          onClick={() => onSelect(conv)}
        >
          <MessageSquare className="w-3.5 h-3.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs truncate">{conv.title}</div>
            <div className="text-[10px] text-muted">
              {new Date(conv.updatedAt).toLocaleDateString('zh-CN')}
            </div>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(conv.id);
            }}
            className="opacity-0 group-hover:opacity-100 text-muted hover:text-red-400 transition-opacity"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
