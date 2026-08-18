/**
 * @file DbStatusBanner 數據庫狀態橫幅 — 在數據庫加載中、未連接或錯誤時，
 * 於頁面頂部顯示醒目的狀態橫幅，讓用戶清楚知道當前數據庫連接情況。
 * 已連接時不顯示（避免佔用空間）。
 */
'use client';

import { useDbHealth } from '@/lib/hooks/useDbHealth';
import { Database, Loader2, AlertTriangle, RefreshCw, Wifi, WifiOff } from 'lucide-react';

/**
 * DbStatusBanner 組件 — 數據庫狀態橫幅。
 * loading → 藍色橫幅 + 旋轉圖標；error/disconnected → 紅色橫幅 + 重試按鈕；connected → 不渲染。
 */
export function DbStatusBanner() {
  const { status, health, error, isLoading, refresh } = useDbHealth();

  // 已連接且表結構正常 → 不顯示橫幅
  if (status === 'connected') return null;

  // loading 中 → 顯示藍色加載橫幅
  if (status === 'loading') {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-accent/30 bg-accent/5 px-4 py-2.5 text-sm">
        <Loader2 className="w-4 h-4 animate-spin text-accent" />
        <Wifi className="w-4 h-4 text-accent" />
        <span className="text-accent">正在连接数据库...</span>
        <span className="text-muted text-xs">检查后端服务与 MySQL 连接</span>
      </div>
    );
  }

  // error 或 disconnected → 顯示紅色錯誤橫幅 + 重試
  const errorMsg = error?.message ?? health?.message ?? '未知原因';
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border border-up/30 bg-up/5 px-4 py-2.5 text-sm">
      <div className="flex items-center gap-2">
        <WifiOff className="w-4 h-4 text-up" />
        <AlertTriangle className="w-4 h-4 text-up" />
        <span className="text-up font-medium">
          {status === 'error' ? '后端服务不可达' : '数据库未连接'}
        </span>
        <span className="text-muted text-xs truncate max-w-[400px]">{errorMsg}</span>
      </div>
      <button
        onClick={() => refresh()}
        disabled={isLoading}
        className="flex items-center gap-1 rounded-md border border-up/30 bg-up/10 px-2.5 py-1 text-xs text-up hover:bg-up/20 transition-colors disabled:opacity-50"
      >
        <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
        重新连接
      </button>
    </div>
  );
}
