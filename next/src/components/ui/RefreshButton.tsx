/**
 * RefreshButton — 帶動畫的刷新按鈕組件。
 *
 * 特性：
 * - 點擊時自動觸發旋轉動畫
 * - 載入中禁用按鈕，防止重複點擊
 * - 支援手動控制 loading 狀態（isValidating）
 * - 延時渲染：點擊後強制最少顯示 600ms 動畫，避免數據秒回導致閃爍
 */
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw } from 'lucide-react';

interface RefreshButtonProps {
  /** 點擊刷新時觸發（通常是 SWR mutate()） */
  onClick: () => unknown | Promise<unknown>;
  /** 外部載入狀態（如 SWR 的 isValidating） */
  isLoading?: boolean;
  /** 按鈕文字，默認「刷新」 */
  label?: string;
  /** 按鈕大小，默認 'sm' */
  size?: 'xs' | 'sm' | 'md';
  /** 額外 className */
  className?: string;
  /** 最小動畫時長（ms），默認 600 */
  minSpinMs?: number;
}

export function RefreshButton({
  onClick,
  isLoading = false,
  label = '刷新',
  size = 'sm',
  className = '',
  minSpinMs = 600,
}: RefreshButtonProps) {
  const [internalSpinning, setInternalSpinning] = useState(false);
  const spinStartTime = useRef<number>(0);
  const minSpinTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 當外部 loading 結束時，檢查是否已達最小動畫時長
  useEffect(() => {
    if (!isLoading && internalSpinning) {
      const elapsed = Date.now() - spinStartTime.current;
      const remaining = Math.max(0, minSpinMs - elapsed);
      if (remaining === 0) {
        setInternalSpinning(false);
      } else {
        minSpinTimer.current = setTimeout(() => {
          setInternalSpinning(false);
        }, remaining);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading]);

  // 清理定時器
  useEffect(() => {
    return () => {
      if (minSpinTimer.current) clearTimeout(minSpinTimer.current);
    };
  }, []);

  const handleClick = useCallback(() => {
    if (internalSpinning || isLoading) return;
    spinStartTime.current = Date.now();
    setInternalSpinning(true);
    onClick();
  }, [internalSpinning, isLoading, onClick]);

  const spinning = internalSpinning || isLoading;

  const sizeClass = size === 'xs' ? 'text-xs px-2 py-1' : size === 'md' ? 'text-sm px-3 py-2' : 'text-xs px-2.5 py-1.5';
  const iconSize = size === 'xs' ? 'w-3 h-3' : size === 'md' ? 'w-4 h-4' : 'w-3.5 h-3.5';

  return (
    <button
      onClick={handleClick}
      disabled={spinning}
      className={`flex items-center gap-1 rounded ${sizeClass} text-slate-400 hover:text-slate-100 hover:bg-bg-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      <RefreshCw className={`${iconSize} ${spinning ? 'animate-spin' : ''}`} />
      {spinning ? '刷新中' : label}
    </button>
  );
}
