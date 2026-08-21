'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown, Check, X, Search } from 'lucide-react';

interface Props {
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  maxheight?: number;
}

export function IndustryMultiSelect({ options, selected, onChange, placeholder = '請選擇', maxheight = 240 }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const filtered = useMemo(() => {
    if (!query) return options;
    const q = query.toLowerCase();
    return options.filter((o) => o.toLowerCase().includes(q));
  }, [options, query]);

  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  const remove = (value: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(selected.filter((v) => v !== value));
  };

  const clearAll = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange([]);
  };

  return (
    <div ref={ref} className="relative">
      <div
        onClick={() => setOpen((v) => !v)}
        className="min-h-[38px] w-full rounded-md border border-border bg-bg-base px-3 py-1.5 flex flex-wrap items-center gap-1 cursor-pointer hover:border-accent/50"
      >
        {selected.length === 0 ? (
          <span className="text-sm text-muted">{placeholder}</span>
        ) : (
          selected.slice(0, 3).map((v) => (
            <span
              key={v}
              className="inline-flex items-center gap-1 rounded bg-accent/10 text-accent text-xs px-1.5 py-0.5 max-w-[180px] truncate"
            >
              {v}
              <X className="w-3 h-3 cursor-pointer" onClick={(e) => remove(v, e)} />
            </span>
          ))
        )}
        {selected.length > 3 && (
          <span className="text-xs text-muted">+{selected.length - 3}</span>
        )}
        {selected.length > 0 && (
          <button
            onClick={clearAll}
            className="ml-auto text-xs text-muted hover:text-slate-200"
            title="清空"
          >
            清空
          </button>
        )}
        <ChevronDown className={`w-4 h-4 text-muted ml-auto transition-transform ${open ? 'rotate-180' : ''}`} />
      </div>

      {open && (
        <div
          className="absolute z-30 mt-1 w-full rounded-md border border-border bg-bg-panel shadow-lg"
          style={{ maxHeight: maxheight }}
        >
          <div className="sticky top-0 p-2 border-b border-border bg-bg-panel">
            <div className="flex items-center gap-2 rounded border border-border bg-bg-base px-2 py-1">
              <Search className="w-3.5 h-3.5 text-muted" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索行業..."
                className="bg-transparent text-sm text-slate-100 outline-none flex-1"
              />
            </div>
          </div>
          <div className="overflow-auto" style={{ maxHeight: maxheight - 50 }}>
            {filtered.length === 0 ? (
              <div className="p-3 text-center text-sm text-muted">無匹配項</div>
            ) : (
              filtered.map((opt) => {
                const checked = selected.includes(opt);
                return (
                  <div
                    key={opt}
                    onClick={() => toggle(opt)}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-200 hover:bg-bg-hover cursor-pointer"
                  >
                    <span
                      className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                        checked ? 'bg-accent border-accent' : 'border-border'
                      }`}
                    >
                      {checked && <Check className="w-3 h-3 text-white" />}
                    </span>
                    <span className="truncate">{opt}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
