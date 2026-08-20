/**
 * @file AgentNodeTimeline 組件 — 節點執行時間軸可視化，
 * 以 ECharts Gantt-style 橫向條形圖展示每輪迭代各節點的執行耗時和狀態，
 * 支持按迭代展開/收起，點擊節點查看詳情。
 */
'use client';

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import ReactECharts from 'echarts-for-react';
import {
  Activity, ChevronDown, ChevronRight, Clock,
  CheckCircle2, XCircle, AlertCircle, Loader2, Gavel,
} from 'lucide-react';
import { agentApi } from '@/lib/api/agent';
import type { TimelineData, TimelineNode } from '@/lib/api/types';

/** 節點顏色映射 */
const NODE_COLORS: Record<string, string> = {
  market_news: '#22d3ee',
  industry_analysis: '#2dd4bf',
  market_analysis: '#60a5fa',
  strategy_generation: '#c084fc',
  backtest: '#fb923c',
  backtest_reflection: '#fbbf24',
  prompt_generation: '#4ade80',
};

/** 狀態顏色 */
const STATUS_COLORS: Record<string, string> = {
  passed: '#22c55e',
  failed: '#ef4444',
  retrying: '#f97316',
  timeout: '#ef4444',
  cancelled: '#6b7280',
  running: '#3b82f6',
  judging: '#f59e0b',
  pending: '#6b7280',
};

/** 節點標籤 */
const NODE_LABELS: Record<string, string> = {
  market_news: '行情新聞',
  industry_analysis: '行業篩選',
  market_analysis: '行情分析',
  strategy_generation: '策略生成',
  backtest: '回測運行',
  backtest_reflection: '回測反思',
  prompt_generation: '提示詞生成',
};

/** 單個節點條 */
function NodeBar({ node }: { node: TimelineNode }) {
  const [showDetail, setShowDetail] = useState(false);
  const color = STATUS_COLORS[node.status] ?? '#6b7280';
  const nodeColor = NODE_COLORS[node.node_id] ?? '#888';
  const label = NODE_LABELS[node.node_id] ?? node.node_id;
  const durationSec = (node.duration_ms / 1000).toFixed(1);

  return (
    <div className="group">
      <button
        onClick={() => setShowDetail(!showDetail)}
        className="w-full flex items-center gap-2 py-1 px-2 rounded hover:bg-bg-base/50 transition-colors text-left"
      >
        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: nodeColor }} />
        <span className="text-xs text-fg w-20 flex-shrink-0">{label}</span>
        <div className="flex-1 relative h-4 bg-bg-base/30 rounded overflow-hidden">
          <div
            className="absolute top-0 left-0 h-full rounded transition-all"
            style={{
              width: `${Math.min((node.duration_ms / 300000) * 100, 100)}%`,
              backgroundColor: color,
              opacity: 0.7,
            }}
          />
          <span className="absolute inset-0 flex items-center px-1.5 text-[10px] text-fg/80">
            {durationSec}s
          </span>
        </div>
        <span className="text-[10px] flex-shrink-0" style={{ color }}>
          {node.status === 'passed' && <CheckCircle2 className="w-3 h-3" />}
          {node.status === 'failed' && <XCircle className="w-3 h-3" />}
          {node.status === 'retrying' && <AlertCircle className="w-3 h-3" />}
          {node.status === 'running' && <Loader2 className="w-3 h-3 animate-spin" />}
          {node.status === 'judging' && <Gavel className="w-3 h-3" />}
        </span>
        {node.judge_score > 0 && (
          <span className="text-[10px] text-amber-400 flex-shrink-0 w-8 text-right">
            {node.judge_score.toFixed(0)}
          </span>
        )}
      </button>
      {showDetail && (
        <div className="ml-6 mb-1 p-2 rounded border border-border bg-bg-base/30 text-[11px] space-y-1">
          <div className="flex gap-4">
            <span className="text-muted">耗時: <span className="text-fg">{durationSec}s</span></span>
            <span className="text-muted">狀態: <span style={{ color }}>{node.status}</span></span>
            {node.attempts > 1 && <span className="text-orange-400">重試 {node.attempts} 次</span>}
          </div>
          {node.judge_score > 0 && (
            <div className="text-muted">
              評委評分: <span className="text-amber-400">{node.judge_score.toFixed(1)}</span>
              <span className={node.judge_passed ? 'text-green-400 ml-2' : 'text-orange-400 ml-2'}>
                {node.judge_passed ? '通過' : '未通過'}
              </span>
            </div>
          )}
          {node.error && (
            <div className="text-red-400 break-all">{node.error}</div>
          )}
          <div className="text-muted">時間: {node.timestamp.slice(11, 19)}</div>
        </div>
      )}
    </div>
  );
}

/**
 * AgentNodeTimeline 組件 — 節點執行時間軸主體。
 * 通過 SWR 輪詢 timeline API，按迭代展示各節點執行條。
 */
export function AgentNodeTimeline() {
  const [expandedIterations, setExpandedIterations] = useState<Set<number>>(new Set([0]));

  const { data: timeline, isValidating } = useSWR<TimelineData>(
    'agent-timeline',
    () => agentApi.monitorTimeline().catch(() => undefined as unknown as TimelineData),
    { refreshInterval: 5000, revalidateOnFocus: false }
  );

  const iterations = timeline?.iterations ?? [];
  const nodeDefs = timeline?.node_definitions ?? [];

  // ECharts 耗時對比圖數據
  const durationChartOption = useMemo(() => {
    if (iterations.length === 0) return null;

    // 計算每個節點的平均耗時
    const nodeDurations: Record<string, number[]> = {};
    const nodeMaxDurations: Record<string, number> = {};
    for (const it of iterations) {
      for (const node of it.nodes) {
        if (!nodeDurations[node.node_id]) {
          nodeDurations[node.node_id] = [];
          nodeMaxDurations[node.node_id] = 0;
        }
        nodeDurations[node.node_id].push(node.duration_ms);
        nodeMaxDurations[node.node_id] = Math.max(
          nodeMaxDurations[node.node_id], node.duration_ms
        );
      }
    }

    const labels = nodeDefs.map(nd => NODE_LABELS[nd.id] ?? nd.id);
    const avgData = nodeDefs.map(nd => {
      const durations = nodeDurations[nd.id];
      if (!durations || durations.length === 0) return 0;
      return Math.round(durations.reduce((a, b) => a + b, 0) / durations.length / 100) / 10;
    });
    const maxData = nodeDefs.map(nd => Math.round(nodeMaxDurations[nd.id] / 100) / 10);

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any[]) => {
          let html = `<div style="font-weight:600;margin-bottom:4px">${params[0].name}</div>`;
          for (const p of params) {
            html += `<div style="color:${p.color}">${p.seriesName}: ${p.value}s</div>`;
          }
          return html;
        },
      },
      legend: {
        data: ['平均耗時', '最長耗時'],
        textStyle: { color: '#94a3b8', fontSize: 11 },
        top: 0,
      },
      grid: { left: '15%', right: '5%', top: 30, bottom: 10 },
      xAxis: {
        type: 'value',
        name: '秒',
        nameTextStyle: { color: '#64748b', fontSize: 10 },
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      yAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: '#cbd5e1', fontSize: 11 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      series: [
        {
          name: '平均耗時',
          type: 'bar',
          data: avgData,
          itemStyle: { color: '#3b82f6', borderRadius: [0, 4, 4, 0] },
          barWidth: '30%',
        },
        {
          name: '最長耗時',
          type: 'bar',
          data: maxData,
          itemStyle: { color: '#f97316', borderRadius: [0, 4, 4, 0] },
          barWidth: '30%',
        },
      ],
    };
  }, [iterations, nodeDefs]);

  if (!timeline || iterations.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-bg-base/30 p-4">
        <div className="flex items-center gap-2 text-muted text-sm">
          <Activity className="w-4 h-4" />
          {isValidating ? '載入時間軸數據中...' : '暫無節點執行記錄'}
        </div>
      </div>
    );
  }

  const toggleIteration = (it: number) => {
    setExpandedIterations(prev => {
      const next = new Set(prev);
      if (next.has(it)) next.delete(it);
      else next.add(it);
      return next;
    });
  };

  return (
    <div className="rounded-lg border border-border bg-bg-base/30 p-4 space-y-3">
      {/* 標題 */}
      <div className="flex items-center gap-2">
        <Activity className="w-4 h-4 text-accent" />
        <span className="text-sm font-medium">節點執行時間軸</span>
        <span className="text-xs text-muted ml-auto">
          {iterations.length} 輪 · {iterations.reduce((a, it) => a + it.nodes.length, 0)} 事件
        </span>
      </div>

      {/* 耗時對比圖 */}
      {durationChartOption && (
        <div className="rounded border border-border bg-bg-base/20 p-2">
          <div className="text-xs text-muted mb-1 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            節點耗時對比（秒）
          </div>
          <ReactECharts
            option={durationChartOption}
            style={{ height: '180px' }}
            opts={{ renderer: 'svg' }}
          />
        </div>
      )}

      {/* 按迭代展開的時間軸 */}
      <div className="space-y-1 max-h-96 overflow-y-auto">
        {iterations.slice().reverse().map((it, itIdx) => {
          const expanded = expandedIterations.has(it.iteration);
          const totalDuration = it.nodes.reduce((a, n) => a + n.duration_ms, 0);
          const passedCount = it.nodes.filter(n => n.status === 'passed').length;
          const failedCount = it.nodes.filter(n => n.status === 'failed').length;

          return (
            <div key={`it-${it.iteration}-${itIdx}`} className="rounded border border-border/50">
              <button
                onClick={() => toggleIteration(it.iteration)}
                className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-bg-base/40 transition-colors text-left"
              >
                {expanded
                  ? <ChevronDown className="w-3 h-3 text-muted" />
                  : <ChevronRight className="w-3 h-3 text-muted" />}
                <span className="text-xs font-medium text-fg">第 {it.iteration + 1} 輪</span>
                <span className="text-[10px] text-muted">
                  {(totalDuration / 1000).toFixed(1)}s · {passedCount} 通過
                  {failedCount > 0 && <span className="text-red-400"> · {failedCount} 失敗</span>}
                </span>
                {/* 迷你進度條 */}
                <div className="flex-1 flex gap-px h-1.5 rounded overflow-hidden">
                  {nodeDefs.map(nd => {
                    const node = it.nodes.find(n => n.node_id === nd.id);
                    if (!node) return <div key={nd.id} className="flex-1 bg-bg-base/30" />;
                    return (
                      <div
                        key={nd.id}
                        className="flex-1 transition-all"
                        style={{
                          backgroundColor: STATUS_COLORS[node.status] ?? '#6b7280',
                          opacity: 0.6,
                        }}
                        title={`${NODE_LABELS[nd.id] ?? nd.id}: ${node.status} (${(node.duration_ms / 1000).toFixed(1)}s)`}
                      />
                    );
                  })}
                </div>
              </button>
              {expanded && (
                <div className="px-2 pb-2 space-y-0.5">
                  {it.nodes.map((node) => (
                    <NodeBar key={node.node_id} node={node} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 圖例 */}
      <div className="flex items-center gap-3 pt-2 border-t border-border text-[10px] text-muted flex-wrap">
        {Object.entries(STATUS_COLORS).filter(([k]) =>
          ['passed', 'failed', 'retrying', 'running', 'judging'].includes(k)
        ).map(([status, color]) => (
          <span key={status} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded" style={{ backgroundColor: color }} />
            {status === 'passed' ? '通過' : status === 'failed' ? '失敗' :
             status === 'retrying' ? '重試' : status === 'running' ? '運行中' : '評委中'}
          </span>
        ))}
        <span className="ml-auto">點擊迭代展開 · 點擊節點查看詳情</span>
      </div>
    </div>
  );
}
