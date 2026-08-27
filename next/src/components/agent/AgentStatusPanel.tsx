/**
 * @file AgentStatusPanel 組件 — Agent 狀態面板，
 * 展示當前輪次、總迭代數、最佳評分、最佳輪次等統計信息和狀態消息。
 */
'use client';

import { Card, CardContent } from '@/components/ui/Card';
import { Activity, TrendingUp, Award, Clock, Loader2 } from 'lucide-react';
import type { AgentState } from '@/lib/api/types';

/** AgentStatusPanel 組件屬性 */
interface Props {
  /** Agent 當前狀態，null 時顯示載入中 */
  state: AgentState | null;
}

/**
 * AgentStatusPanel 組件 — 以統計卡片形式展示 Agent 運行狀態。
 * @param state Agent 當前狀態
 */
export function AgentStatusPanel({ state }: Props) {
  if (!state) {
    return (
      <div className="flex items-center justify-center py-6 text-muted text-sm">
        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
        載入狀態中...
      </div>
    );
  }

  const stats = [
    {
      label: '當前輪次',
      value: state.current_iteration || '-',
      icon: Activity,
      color: 'text-blue-400',
    },
    {
      label: '總迭代數',
      value: state.total_iterations,
      icon: Clock,
      color: 'text-slate-400',
    },
    {
      label: '最佳評分',
      value: state.best_score > -999 ? state.best_score.toFixed(1) : '-',
      icon: Award,
      color: 'text-amber-400',
    },
    {
      label: '最佳輪次',
      value: state.best_iteration || '-',
      icon: TrendingUp,
      color: 'text-green-400',
    },
  ];

  return (
    <div className="space-y-3">
      {/* 統計卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="rounded-lg border border-border bg-bg-base/50 p-3">
              <div className="flex items-center gap-1.5 text-xs text-muted mb-1">
                <Icon className={`w-3 h-3 ${s.color}`} />
                {s.label}
              </div>
              <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
            </div>
          );
        })}
      </div>

      {/* 狀態消息 */}
      {state.status_message && state.status_message !== 'idle' && (
        <div className={`flex items-center gap-2 rounded p-2.5 text-sm ${
          state.running
            ? 'bg-blue-500/10 text-blue-300 border border-blue-500/20'
            : 'bg-bg-hover text-muted'
        }`}>
          {state.running && <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />}
          <span>{state.status_message}</span>
        </div>
      )}

      {/* 時間信息 */}
      <div className="flex flex-wrap gap-4 text-xs text-muted">
        {state.started_at && (
          <span>啟動時間: {new Date(state.started_at).toLocaleString('zh-TW')}</span>
        )}
        {state.stopped_at && (
          <span>停止時間: {new Date(state.stopped_at).toLocaleString('zh-TW')}</span>
        )}
      </div>
    </div>
  );
}
