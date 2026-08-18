/**
 * @file AgentMonitorPanel 組件 — Agent 系統監控面板，
 * 實時展示節點統計、活躍告警、評分趨勢和最近事件，支持 AI 診斷。
 */
'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  Activity, AlertCircle, AlertTriangle, CheckCircle2, XCircle,
  Clock, Loader2, Brain, TrendingDown, Zap, RefreshCw,
} from 'lucide-react';
import { agentApi } from '@/lib/api/agent';
import type { MonitorStatus, MonitorAnalysis, MonitorAlert } from '@/lib/api/types';

/** 告警級別圖標 */
function AlertIcon({ level }: { level: string }) {
  if (level === 'critical') return <XCircle className="w-4 h-4 text-red-400" />;
  if (level === 'warning') return <AlertTriangle className="w-4 h-4 text-amber-400" />;
  return <AlertCircle className="w-4 h-4 text-blue-400" />;
}

/** 健康狀態徽章 */
function HealthBadge({ health }: { health: string }) {
  const config: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
    healthy: { color: 'text-green-400 bg-green-500/10 border-green-500/30', icon: CheckCircle2, label: '健康' },
    warning: { color: 'text-amber-400 bg-amber-500/10 border-amber-500/30', icon: AlertTriangle, label: '警告' },
    critical: { color: 'text-red-400 bg-red-500/10 border-red-500/30', icon: XCircle, label: '嚴重' },
    idle: { color: 'text-muted bg-bg-base/30 border-border', icon: Activity, label: '空閒' },
  };
  const c = config[health] ?? config.idle;
  const Icon = c.icon;
  return (
    <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${c.color}`}>
      <Icon className="w-3 h-3" />
      {c.label}
    </span>
  );
}

/** 單個告警卡片 */
function AlertCard({ alert, onResolve }: { alert: MonitorAlert; onResolve: () => void }) {
  return (
    <div className={`flex items-start gap-2 rounded border p-2 text-xs ${
      alert.level === 'critical'
        ? 'border-red-500/20 bg-red-500/5'
        : alert.level === 'warning'
        ? 'border-amber-500/20 bg-amber-500/5'
        : 'border-blue-500/20 bg-blue-500/5'
    }`}>
      <AlertIcon level={alert.level} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-fg">{alert.category}</span>
          <span className="text-muted">節點: {alert.node_id}</span>
          <span className="text-muted ml-auto">{alert.timestamp.slice(11, 19)}</span>
        </div>
        <p className="text-fg/80 mt-1 break-words">{alert.message}</p>
        {alert.suggestion && (
          <p className="text-muted mt-1 italic">建議: {alert.suggestion}</p>
        )}
      </div>
      {!alert.resolved && (
        <button
          onClick={onResolve}
          className="text-muted hover:text-green-400 transition-colors flex-shrink-0"
          title="標記為已解決"
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}

/** 節點統計卡片 */
function NodeStatCard({ nodeId, stats }: { nodeId: string; stats: import('@/lib/api/types').NodeStats }) {
  const labels: Record<string, string> = {
    market_news: '行情新聞',
    industry_analysis: '行業篩選',
    market_analysis: '行情分析',
    strategy_generation: '策略生成',
    backtest: '回測',
    backtest_reflection: '回測反思',
    prompt_generation: '提示詞生成',
  };
  const label = labels[nodeId] ?? nodeId;
  const avgSec = (stats.avg_duration_ms / 1000).toFixed(1);
  const maxSec = (stats.max_duration_ms / 1000).toFixed(1);
  const failureRate = stats.total_runs > 0 ? (stats.failures / stats.total_runs * 100).toFixed(0) : '0';

  return (
    <div className="rounded border border-border bg-bg-base/30 p-2 text-xs">
      <div className="font-medium text-fg mb-1">{label}</div>
      <div className="grid grid-cols-2 gap-1 text-muted">
        <span>運行: <span className="text-fg">{stats.total_runs}</span></span>
        <span>平均: <span className="text-fg">{avgSec}s</span></span>
        <span>最慢: <span className="text-fg">{maxSec}s</span></span>
        <span>失敗: <span className={stats.failures > 0 ? 'text-red-400' : 'text-fg'}>{stats.failures} ({failureRate}%)</span></span>
        <span>重試: <span className={stats.retries > 0 ? 'text-orange-400' : 'text-fg'}>{stats.retries}</span></span>
        <span>評委均分: <span className="text-fg">{stats.avg_judge_score}</span></span>
      </div>
    </div>
  );
}

/**
 * AgentMonitorPanel 組件 — 系統監控面板主體。
 * 通過 SWR 每 5 秒輪詢監控狀態，支持 AI 診斷和告警解決操作。
 */
export function AgentMonitorPanel() {
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<MonitorAnalysis | null>(null);

  // 輪詢監控狀態
  const { data: monitor, mutate: refreshMonitor } = useSWR<MonitorStatus>(
    'agent-monitor',
    () => agentApi.monitor().catch(() => undefined as unknown as MonitorStatus),
    { refreshInterval: 5000, revalidateOnFocus: false }
  );

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const result = await agentApi.monitorAnalyze();
      setAnalysis(result);
    } catch (e) {
      setAnalysis({
        analysis: `分析失敗: ${(e as Error).message}`,
        health: 'idle',
        suggestions: [],
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleResolve = async (alertId: string) => {
    try {
      await agentApi.resolveAlert(alertId);
      await refreshMonitor();
    } catch (e) {
      console.error('解決告警失敗:', e);
    }
  };

  if (!monitor) {
    return (
      <div className="rounded-lg border border-border bg-bg-base/30 p-4">
        <div className="flex items-center gap-2 text-muted text-sm">
          <Activity className="w-4 h-4" />
          監控數據載入中...
        </div>
      </div>
    );
  }

  const activeAlerts = monitor.active_alert_list ?? [];
  const nodeStats = monitor.node_stats ?? {};
  const recentEvents = monitor.recent_events ?? [];
  const scoreHistory = monitor.score_history ?? [];

  return (
    <div className="rounded-lg border border-border bg-bg-base/30 p-4 space-y-3">
      {/* 標題 + 健康狀態 */}
      <div className="flex items-center gap-2 flex-wrap">
        <Activity className="w-4 h-4 text-accent" />
        <span className="text-sm font-medium">系統監控</span>
        <HealthBadge health={analysis?.health ?? (monitor.critical_alerts > 0 ? 'critical' : monitor.warning_alerts > 0 ? 'warning' : 'healthy')} />
        <span className="text-xs text-muted">
          run: {monitor.run_id?.slice(-8) || '—'}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-border hover:border-accent/50 transition-colors"
          >
            {analyzing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Brain className="w-3 h-3" />}
            AI 診斷
          </button>
          <button
            onClick={() => refreshMonitor()}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-border hover:border-accent/50 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* 概覽統計 */}
      <div className="grid grid-cols-4 gap-2 text-xs">
        <div className="rounded border border-border bg-bg-base/30 p-2 text-center">
          <div className="text-muted">事件</div>
          <div className="text-lg font-bold text-fg">{monitor.total_events}</div>
        </div>
        <div className="rounded border border-border bg-bg-base/30 p-2 text-center">
          <div className="text-muted">活躍告警</div>
          <div className={`text-lg font-bold ${monitor.active_alerts > 0 ? 'text-amber-400' : 'text-green-400'}`}>
            {monitor.active_alerts}
          </div>
        </div>
        <div className="rounded border border-border bg-bg-base/30 p-2 text-center">
          <div className="text-muted">嚴重</div>
          <div className={`text-lg font-bold ${monitor.critical_alerts > 0 ? 'text-red-400' : 'text-green-400'}`}>
            {monitor.critical_alerts}
          </div>
        </div>
        <div className="rounded border border-border bg-bg-base/30 p-2 text-center">
          <div className="text-muted">警告</div>
          <div className={`text-lg font-bold ${monitor.warning_alerts > 0 ? 'text-amber-400' : 'text-green-400'}`}>
            {monitor.warning_alerts}
          </div>
        </div>
      </div>

      {/* 活躍告警 */}
      {activeAlerts.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-medium text-muted flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            活躍告警 ({activeAlerts.length})
          </div>
          {activeAlerts.map((alert) => (
            <AlertCard key={alert.alert_id} alert={alert} onResolve={() => handleResolve(alert.alert_id)} />
          ))}
        </div>
      )}

      {/* 節點統計 */}
      {Object.keys(nodeStats).length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-medium text-muted flex items-center gap-1">
            <Zap className="w-3 h-3" />
            節點性能統計
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">
            {Object.entries(nodeStats).map(([nodeId, stats]) => (
              <NodeStatCard key={nodeId} nodeId={nodeId} stats={stats} />
            ))}
          </div>
        </div>
      )}

      {/* 評分趨勢 */}
      {scoreHistory.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-medium text-muted flex items-center gap-1">
            <TrendingDown className="w-3 h-3" />
            評分歷史 ({scoreHistory.length} 輪)
          </div>
          <div className="flex items-end gap-0.5 h-8">
            {scoreHistory.map((score, i) => {
              const maxScore = Math.max(...scoreHistory, 1);
              const height = `${Math.max((score / maxScore) * 100, 5)}%`;
              return (
                <div
                  key={i}
                  className="flex-1 bg-accent/40 rounded-t"
                  style={{ height }}
                  title={`第 ${i + 1} 輪: ${score}`}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* 最近事件 */}
      {recentEvents.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-muted hover:text-fg transition-colors flex items-center gap-1">
            <Clock className="w-3 h-3" />
            最近事件 ({recentEvents.length})
          </summary>
          <div className="mt-1.5 space-y-0.5 max-h-40 overflow-y-auto">
            {recentEvents.slice(-15).reverse().map((e, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px] text-muted py-0.5">
                <span className="text-fg/60">{e.timestamp.slice(11, 19)}</span>
                <span className="font-medium text-fg">{e.node_id}</span>
                <span className={
                  e.status === 'passed' ? 'text-green-400' :
                  e.status === 'failed' ? 'text-red-400' :
                  e.status === 'running' ? 'text-blue-400' :
                  e.status === 'judging' ? 'text-amber-400' :
                  e.status === 'retrying' ? 'text-orange-400' :
                  'text-muted'
                }>{e.status}</span>
                {e.duration_ms > 0 && <span>{(e.duration_ms / 1000).toFixed(1)}s</span>}
                {e.judge_score > 0 && <span className="text-amber-400">評委:{e.judge_score}</span>}
              </div>
            ))}
          </div>
        </details>
      )}

      {/* AI 診斷結果 */}
      {analysis && (
        <div className="rounded border border-accent/20 bg-accent/5 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-accent" />
            <span className="text-sm font-medium">AI 診斷結果</span>
            <HealthBadge health={analysis.health} />
          </div>
          <pre className="whitespace-pre-wrap break-words text-xs text-fg/80 leading-relaxed">
            {analysis.analysis}
          </pre>
          {analysis.suggestions.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-muted">建議操作:</div>
              {analysis.suggestions.map((s, i) => (
                <div key={i} className="text-xs text-fg/80 flex items-start gap-1">
                  <span className="text-accent">•</span>
                  {s}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
