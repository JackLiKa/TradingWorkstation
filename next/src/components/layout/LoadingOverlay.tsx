/**
 * @file LoadingOverlay 全屏加載遮罩 — 當全局 loading 狀態為 true 時，
 * 顯示半透明遮罩和旋轉加載圖標，阻止用戶操作。
 */
'use client';

import { useLoadingStore } from '@/lib/store/loading';
import { Loader2 } from 'lucide-react';

/**
 * LoadingOverlay 組件 — 監聽 Zustand loading store，激活時顯示全屏遮罩。
 * @returns loading 為 true 時返回遮罩 JSX，否則返回 null
 */
export function LoadingOverlay() {
  const loading = useLoadingStore((s) => s.loading);
  const message = useLoadingStore((s) => s.message);
  if (!loading) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="flex items-center gap-3 rounded-lg border border-border bg-bg-panel px-6 py-4 shadow-xl">
        <Loader2 className="w-5 h-5 animate-spin text-accent" />
        <span className="text-sm text-slate-200">{message || '加载中...'}</span>
      </div>
    </div>
  );
}
