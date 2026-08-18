/**
 * @file StockSearchInput 組件 — 股票搜索輸入框，帶防抖自動補全下拉建議，
 * 支持鍵盤導航（上下箭頭 + Enter 選中 + Escape 關閉）。
 */
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '@/lib/api';
import type { StockSuggestionDto } from '@/lib/api/types';
import { formatPercent, pctClass } from '@/lib/format';
import { Search, Loader2 } from 'lucide-react';

/** StockSearchInput 組件屬性 */
interface StockSearchInputProps {
  /** 當前輸入值 */
  value: string;
  /** 輸入值變化回調 */
  onChange: (value: string) => void;
  /** 選中建議項回調（傳入股票代碼） */
  onSelect: (code: string) => void;
  /** 輸入框 placeholder */
  placeholder?: string;
  /** 額外的 CSS 類名 */
  className?: string;
}

/**
 * StockSearchInput 組件 — 帶自動補全的股票搜索輸入框。
 * 輸入時防抖 200ms 後調用 suggest API 獲取建議列表，支持鍵盤導航。
 * @param value 當前輸入值
 * @param onChange 輸入變化回調
 * @param onSelect 選中建議回調
 * @param placeholder 輸入框佔位文字
 * @param className 額外 CSS 類名
 */
export function StockSearchInput({
  value,
  onChange,
  onSelect,
  placeholder = 'sh.600000 / 600000 / 600',
  className = '',
}: StockSearchInputProps) {
  const [suggestions, setSuggestions] = useState<StockSuggestionDto[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 防抖獲取建議
  const fetchSuggestions = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q || q.trim().length < 1) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const result = await api.suggest(q.trim(), 10);
        setSuggestions(result);
        setOpen(result.length > 0);
        setHighlightIndex(-1);
      } catch {
        setSuggestions([]);
        setOpen(false);
      } finally {
        setLoading(false);
      }
    }, 200);
  }, []);

  // 輸入變化時觸發建議
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    onChange(v);
    fetchSuggestions(v);
  };

  // 選中某個建議
  const selectSuggestion = (code: string) => {
    onChange(code);
    onSelect(code);
    setOpen(false);
    setSuggestions([]);
  };

  // 鍵盤導航
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIndex((prev) => (prev + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIndex((prev) => (prev - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === 'Enter' && highlightIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[highlightIndex].code);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  // 點擊外部關閉下拉
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted pointer-events-none" />
        <input
          type="text"
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => { if (suggestions.length > 0) setOpen(true); }}
          placeholder={placeholder}
          className="flex h-9 w-full rounded-md border border-border bg-bg-card pl-8 pr-7 py-1 text-sm text-slate-200 placeholder:text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent disabled:opacity-50"
        />
        {loading && (
          <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted animate-spin" />
        )}
      </div>

      {open && suggestions.length > 0 && (
        <div className="absolute z-50 mt-1 w-full min-w-[280px] rounded-md border border-border bg-bg-panel shadow-lg max-h-[320px] overflow-auto">
          {suggestions.map((s, i) => (
            <div
              key={s.code}
              className={`flex items-center justify-between px-3 py-2 text-sm cursor-pointer transition-colors ${
                i === highlightIndex ? 'bg-accent/10 text-accent' : 'text-slate-200 hover:bg-bg-hover'
              }`}
              onClick={() => selectSuggestion(s.code)}
              onMouseEnter={() => setHighlightIndex(i)}
            >
              <span className="font-mono">{s.code}</span>
              <span className="flex items-center gap-3">
                {s.closePrice != null && (
                  <span className="tabular-nums text-slate-300">{s.closePrice.toFixed(2)}</span>
                )}
                {s.pctChange != null && (
                  <span className={`tabular-nums text-xs ${pctClass(s.pctChange)}`}>
                    {formatPercent(s.pctChange)}
                  </span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
