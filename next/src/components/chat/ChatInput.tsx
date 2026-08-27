'use client';

/**
 * @file ChatInput — 聊天输入框 + 模型选择器。
 */

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatProvider } from '@/lib/api/chat';

interface ChatInputProps {
  onSend: (content: string) => void;
  disabled: boolean;
  providers: ChatProvider[];
  selectedProvider: string;
  onProviderChange: (provider: string) => void;
}

export function ChatInput({ onSend, disabled, providers, selectedProvider, onProviderChange }: ChatInputProps) {
  const [input, setInput] = useState('');
  const [showProviderMenu, setShowProviderMenu] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 自动调整 textarea 高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 100) + 'px';
    }
  }, [input]);

  const selectedProviderInfo = providers.find(p => p.provider === selectedProvider);

  return (
    <div className="border-t border-border p-3 space-y-2">
      {/* 模型选择器 */}
      <div className="relative">
        <button
          onClick={() => setShowProviderMenu(!showProviderMenu)}
          className="flex items-center gap-1 text-xs text-muted hover:text-slate-200 px-2 py-1 rounded border border-border bg-bg"
        >
          <span>{selectedProviderInfo ? selectedProviderInfo.display_name : '自动选择模型'}</span>
          <ChevronDown className="w-3 h-3" />
        </button>
        {showProviderMenu && (
          <div className="absolute bottom-full left-0 mb-1 w-56 bg-bg-panel border border-border rounded-lg shadow-xl max-h-60 overflow-auto z-10">
            <button
              onClick={() => { onProviderChange(''); setShowProviderMenu(false); }}
              className={cn(
                'w-full text-left px-3 py-2 text-xs hover:bg-bg-hover',
                selectedProvider === '' ? 'text-accent' : 'text-slate-300'
              )}
            >
              自动选择（推荐）
            </button>
            {providers.map(p => (
              <button
                key={p.provider}
                onClick={() => { onProviderChange(p.provider); setShowProviderMenu(false); }}
                className={cn(
                  'w-full text-left px-3 py-2 text-xs hover:bg-bg-hover',
                  selectedProvider === p.provider ? 'text-accent' : 'text-slate-300',
                  !p.available && 'opacity-50 cursor-not-allowed'
                )}
                disabled={!p.available}
              >
                <div className="flex items-center justify-between">
                  <span>{p.display_name}</span>
                  {p.is_free && <span className="text-green-400 text-[10px]">免费</span>}
                </div>
                {p.description && (
                  <div className="text-[10px] text-muted mt-0.5">{p.description}</div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 输入框 + 发送按钮 */}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的问题..."
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-bg border border-border rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-muted focus:outline-none focus:border-accent/50 max-h-24"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || disabled}
          className={cn(
            'flex items-center justify-center w-8 h-8 rounded-lg transition-colors',
            input.trim() && !disabled
              ? 'bg-accent text-white hover:bg-accent/90'
              : 'bg-bg-hover text-muted cursor-not-allowed'
          )}
        >
          {disabled ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}
