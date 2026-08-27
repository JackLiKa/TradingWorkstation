/**
 * @file Topbar 頂部欄組件 — 顯示應用標題和數據庫連接狀態徽章，
 * 使用全局 useDbHealth hook 共享 SWR 緩存，帶動畫圖標和連接詳情。
 */
'use client';

import { Badge } from '@/components/ui/Badge';
import { useDbHealth } from '@/lib/hooks/useDbHealth';
import { Database, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';

/**
 * Topbar 組件 — 顯示數據庫連接狀態（帶圖標動畫）和表結構校驗結果。
 * @returns 頂部欄 JSX，包含標題和數據庫狀態徽章
 */
export function Topbar() {
  const { status, health, isLoading } = useDbHealth();

  const connected = health?.connected ?? false;
  const schemaValid = health?.schemaValid ?? false;
  const dbName = health?.databaseName ?? '';
  const dbHost = health?.host ?? '';
  const dbPort = health?.port ?? '';

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-bg-panel px-3 md:px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-base md:text-lg font-semibold text-slate-100">量化交易工作台</h1>
      </div>
      <div className="flex items-center gap-2">
        {/* 數據庫連接狀態 — 可視化圖標 + 文字 + tooltip */}
        {status === 'loading' ? (
          <Badge variant="info" className="gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            数据库连接中...
          </Badge>
        ) : status === 'error' ? (
          <Badge variant="danger" className="gap-1.5" title="后端服务不可达">
            <AlertTriangle className="w-3.5 h-3.5" />
            后端不可达
          </Badge>
        ) : connected ? (
          <Badge variant="success" className="gap-1.5" title={`${dbHost}:${dbPort}/${dbName}`}>
            <CheckCircle2 className="w-3.5 h-3.5" />
            数据库已连接
          </Badge>
        ) : (
          <Badge variant="danger" className="gap-1.5" title={health?.message ?? '未知原因'}>
            <Database className="w-3.5 h-3.5" />
            数据库未连接
          </Badge>
        )}

        {/* 表結構校驗 — 僅在已連接時顯示 */}
        {connected && (
          <Badge variant={schemaValid ? 'info' : 'warning'} className="gap-1.5">
            {schemaValid ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
            {schemaValid ? '表结构正常' : '表结构异常'}
          </Badge>
        )}

        {/* 數據庫名稱 */}
        {dbName && (
          <span className="hidden md:inline text-xs text-muted truncate max-w-[280px]">
            {dbHost}:{dbPort}/{dbName}
          </span>
        )}
      </div>
    </header>
  );
}
