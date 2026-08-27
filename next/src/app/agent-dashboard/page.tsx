/**
 * @file AgentDashboardPage — AI 調用可觀測性儀表板。
 * 展示每輪所有 AI 的分數得分趨勢圖、調用鏈詳情（可展開查看 input/output）。
 * 支持按迭代輪次和階段過濾，數據圖量化顯示。
 */
'use client';

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Select } from '@/components/ui/Select';
import { ErrorState } from '@/components/ui/ErrorState';
import { api } from '@/lib/api';
import { agentApi } from '@/lib/api/agent';
import type { AiCallLog, ScoreTrend, AvailableProvider } from '@/lib/api/types';
import { ChevronDown, ChevronRight, Activity, Cpu, Clock, CheckCircle, XCircle } from 'lucide-react';
import { RefreshButton } from '@/components/ui/RefreshButton';

/** 階段顯示名稱映射 */
const STAGE_LABELS: Record<string, string> = {
  market_news: 'AI 0 · 行情新聞',
  industry_analysis: 'AI 0.5 · 行業分析',
  market_analysis: 'AI 1 · 行情分析',
  strategy_generation: 'AI 2 · 策略生成',
  backtest_reflection: 'AI 3 · 回測反思',
  prompt_generation: 'AI 4 · 提示詞生成',
  judge: '評委 AI',
};

/** 供應商顯示名稱 */
const PROVIDER_LABELS: Record<string, string> = {
  qoder: 'Qoder Lite',
  devin: 'Devin GLM-5.2',
  none: '不可用',
  unknown: '未知',
};

export default function AgentDashboardPage() {
  const [selectedIteration, setSelectedIteration] = useState<number | null>(null);
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);
  const [stageFilter, setStageFilter] = useState<string>('');

  // 評分趨勢
  const { data: trend, error: trendError, mutate: mutateTrend } = useSWR<ScoreTrend>(
    'score-trend',
    () => api.scoreTrend(),
    { refreshInterval: 10000 }
  );

  // 最近日誌
  const { data: recentLogs, error: logsError } = useSWR<AiCallLog[]>(
    'recent-logs',
    () => api.recentAiCallLogs(20),
    { refreshInterval: 5000 }
  );

  // 按迭代的調用鏈
  const { data: iterationLogs, error: iterationError } = useSWR<AiCallLog[]>(
    selectedIteration ? `iteration-${selectedIteration}` : null,
    () => api.aiCallLogsByIteration(selectedIteration!),
    { refreshInterval: 5000 }
  );

  // 供應商狀態
  const { data: providers } = useSWR('providers', () => agentApi.getProviders(), { refreshInterval: 30000 });

  const maxIteration = trend?.maxIteration ?? 0;
  const iterations = useMemo(() => {
    const arr = [];
    for (let i = 1; i <= maxIteration; i++) arr.push(i);
    return arr;
  }, [maxIteration]);

  const displayLogs = selectedIteration ? (iterationLogs ?? []) : (recentLogs ?? []);
  const filteredLogs = stageFilter ? displayLogs.filter((l) => l.stageName === stageFilter) : displayLogs;

  return (
    <div className="space-y-6">
      {/* 頁面標題 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Activity className="w-6 h-6 text-accent" />
          <h1 className="text-xl font-bold text-slate-100">Agent Dashboard</h1>
          <Badge variant="info">AI 可觀測性</Badge>
        </div>
        <RefreshButton onClick={() => mutateTrend()} />
      </div>

      {/* 供應商狀態卡片 */}
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Cpu className="w-4 h-4" /> LLM 供應商狀態</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {providers?.providers.map((p: AvailableProvider) => (
              <div key={p.provider} className="flex items-center justify-between p-3 rounded-md border border-border bg-bg-hover">
                <div>
                  <div className="text-sm font-medium text-slate-200">{PROVIDER_LABELS[p.provider] ?? p.provider}</div>
                  <div className="text-xs text-muted">{p.model}</div>
                </div>
                <Badge variant={p.available ? 'success' : 'danger'}>
                  {p.available ? '可用' : '不可用'}
                </Badge>
              </div>
            ))}
            {(!providers || providers.providers.length === 0) && (
              <div className="text-sm text-muted col-span-2">載入中...</div>
            )}
          </div>
          {providers?.stage_preferences && Object.keys(providers.stage_preferences).length > 0 && (
            <div className="mt-3 pt-3 border-t border-border-subtle">
              <div className="text-xs text-muted mb-2">階段供應商偏好：</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(providers.stage_preferences).map(([stage, provider]) => (
                  <Badge key={stage} variant="default">
                    {STAGE_LABELS[stage as string] ?? stage}: {PROVIDER_LABELS[provider as string] ?? provider}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 評分趨勢圖 */}
      <Card>
        <CardHeader><CardTitle>評分趨勢（每輪平均評分）</CardTitle></CardHeader>
        <CardContent>
          {trendError ? (
            <ErrorState message="無法載入評分趨勢" onRetry={() => mutateTrend()} />
          ) : !trend || trend.iterationTrends.length === 0 ? (
            <div className="text-sm text-muted py-8 text-center">暫無評分數據（Agent 未運行或無調用日誌）</div>
          ) : (
            <ScoreTrendChart trend={trend} />
          )}
        </CardContent>
      </Card>

      {/* 各階段評分對比圖 */}
      <Card>
        <CardHeader><CardTitle>各階段評分對比</CardTitle></CardHeader>
        <CardContent>
          {trend && trend.stageTrends.length > 0 ? (
            <StageScoreChart trend={trend} />
          ) : (
            <div className="text-sm text-muted py-8 text-center">暫無階段評分數據</div>
          )}
        </CardContent>
      </Card>

      {/* 調用鏈詳情 */}
      <Card>
        <CardHeader>
          <CardTitle>調用鏈詳情</CardTitle>
          <div className="flex gap-2 flex-wrap">
            <Select
              value={selectedIteration?.toString() ?? ''}
              onChange={(e) => setSelectedIteration(e.target.value ? Number(e.target.value) : null)}
              className="w-40"
            >
              <option value="">最近 20 條</option>
              {iterations.map((i) => (
                <option key={i} value={i}>第 {i} 輪</option>
              ))}
            </Select>
            <Select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              className="w-48"
            >
              <option value="">全部階段</option>
              {trend?.stages.map((s) => (
                <option key={s} value={s}>{STAGE_LABELS[s] ?? s}</option>
              ))}
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {(logsError || iterationError) && (
            <ErrorState message="無法載入調用日誌" onRetry={() => {}} />
          )}
          {!filteredLogs || filteredLogs.length === 0 ? (
            <div className="text-sm text-muted py-8 text-center">暫無調用日誌</div>
          ) : (
            <div className="space-y-2">
              {filteredLogs.map((log) => (
                <LogEntry
                  key={log.id}
                  log={log}
                  expanded={expandedLogId === log.id}
                  onToggle={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/** 評分趨勢折線圖（純 CSS/SVG，不依賴 ECharts） */
function ScoreTrendChart({ trend }: { trend: ScoreTrend }) {
  const points = trend.iterationTrends;
  if (points.length === 0) return null;

  const width = 800;
  const height = 200;
  const padding = 40;
  const maxScore = 100;
  const xStep = (width - padding * 2) / Math.max(points.length - 1, 1);

  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${padding + i * xStep} ${height - padding - (p.avgScore / maxScore) * (height - padding * 2)}`)
    .join(' ');

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ minWidth: 400 }}>
        {/* 網格線 */}
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line
              x1={padding} y1={height - padding - (v / maxScore) * (height - padding * 2)}
              x2={width - padding} y2={height - padding - (v / maxScore) * (height - padding * 2)}
              stroke="rgb(51,65,85)" strokeWidth="0.5" strokeDasharray="2,2"
            />
            <text x={5} y={height - padding - (v / maxScore) * (height - padding * 2) + 4} fill="rgb(148,163,184)" fontSize="10">
              {v}
            </text>
          </g>
        ))}
        {/* 折線 */}
        <path d={pathD} fill="none" stroke="rgb(59,130,246)" strokeWidth="2" />
        {/* 數據點 */}
        {points.map((p, i) => (
          <g key={i}>
            <circle
              cx={padding + i * xStep}
              cy={height - padding - (p.avgScore / maxScore) * (height - padding * 2)}
              r="4" fill="rgb(59,130,246)"
            />
            <text
              x={padding + i * xStep}
              y={height - padding + 15}
              fill="rgb(148,163,184)" fontSize="10" textAnchor="middle"
            >
              第{p.iteration}輪
            </text>
            <text
              x={padding + i * xStep}
              y={height - padding - (p.avgScore / maxScore) * (height - padding * 2) - 8}
              fill="rgb(226,232,240)" fontSize="10" textAnchor="middle"
            >
              {p.avgScore.toFixed(1)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

/** 各階段評分柱狀圖 */
function StageScoreChart({ trend }: { trend: ScoreTrend }) {
  // 按階段聚合平均分
  const stageAvgs: Record<string, number[]> = {};
  trend.stageTrends.forEach((p) => {
    if (!stageAvgs[p.stageName]) stageAvgs[p.stageName] = [];
    stageAvgs[p.stageName].push(p.avgScore);
  });
  const stages = Object.entries(stageAvgs).map(([name, scores]) => ({
    name,
    label: STAGE_LABELS[name] ?? name,
    avg: scores.reduce((a, b) => a + b, 0) / scores.length,
  }));

  return (
    <div className="space-y-2">
      {stages.map((s) => (
        <div key={s.name} className="flex items-center gap-3">
          <div className="w-32 text-xs text-slate-300 truncate">{s.label}</div>
          <div className="flex-1 bg-bg-hover rounded-full h-6 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 flex items-center justify-end pr-2"
              style={{ width: `${Math.max(s.avg, 2)}%` }}
            >
              <span className="text-xs text-white font-medium">{s.avg.toFixed(1)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/** 單條調用日誌 — 可展開查看 input/output */
function LogEntry({ log, expanded, onToggle }: { log: AiCallLog; expanded: boolean; onToggle: () => void }) {
  const inputJson = (() => {
    try { return JSON.parse(log.inputJson); } catch { return null; }
  })();
  const outputJson = (() => {
    try { return JSON.parse(log.outputJson); } catch { return null; }
  })();

  return (
    <div className="border border-border rounded-md overflow-hidden">
      {/* 摺疊標題 */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-3 hover:bg-bg-hover transition-colors text-left"
      >
        {expanded ? <ChevronDown className="w-4 h-4 text-muted" /> : <ChevronRight className="w-4 h-4 text-muted" />}
        <Badge variant="default">第{log.iteration}輪</Badge>
        <span className="text-sm text-slate-200 flex-1 truncate">
          {STAGE_LABELS[log.stageName] ?? log.stageName}
        </span>
        <Badge variant={log.provider === 'qoder' ? 'info' : log.provider === 'devin' ? 'success' : 'default'}>
          {PROVIDER_LABELS[log.provider] ?? log.provider}
        </Badge>
        {log.judgePassed !== null && (
          <Badge variant={log.judgePassed ? 'success' : 'danger'}>
            {log.judgePassed ? <CheckCircle className="w-3 h-3 inline mr-1" /> : <XCircle className="w-3 h-3 inline mr-1" />}
            {log.judgeScore?.toFixed(1) ?? '-'}
          </Badge>
        )}
        <span className="text-xs text-muted flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {log.durationMs}ms
        </span>
      </button>

      {/* 展開內容 */}
      {expanded && (
        <div className="border-t border-border p-4 space-y-3 bg-bg-panel">
          {/* 元數據 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <MetaItem label="階段" value={log.stageDisplayName ?? log.stageName} />
            <MetaItem label="供應商" value={PROVIDER_LABELS[log.provider] ?? log.provider} />
            <MetaItem label="模型" value={log.modelName} />
            <MetaItem label="嘗試次數" value={log.attempts.toString()} />
            <MetaItem label="耗時" value={`${log.durationMs}ms`} />
            <MetaItem label="評委評分" value={log.judgeScore?.toFixed(1) ?? '-'} />
            <MetaItem label="評委通過" value={log.judgePassed === null ? '-' : log.judgePassed ? '是' : '否'} />
            <MetaItem label="時間" value={new Date(log.createdAt).toLocaleString()} />
          </div>

          {/* 評委反饋 */}
          {log.judgeFeedback && (
            <div>
              <div className="text-xs text-muted mb-1">評委反饋：</div>
              <pre className="text-xs text-slate-300 bg-bg-hover p-2 rounded overflow-x-auto whitespace-pre-wrap">
                {log.judgeFeedback}
              </pre>
            </div>
          )}

          {/* 錯誤信息 */}
          {log.error && (
            <div>
              <div className="text-xs text-red-400 mb-1">錯誤：</div>
              <pre className="text-xs text-red-300 bg-red-950/30 p-2 rounded overflow-x-auto whitespace-pre-wrap">
                {log.error}
              </pre>
            </div>
          )}

          {/* 標準化輸入 */}
          {inputJson && (
            <div>
              <div className="text-xs text-muted mb-1">標準化輸入（JSON）：</div>
              <pre className="text-xs text-slate-300 bg-bg-hover p-2 rounded overflow-x-auto max-h-60">
                {JSON.stringify(inputJson, null, 2)}
              </pre>
            </div>
          )}

          {/* AI 原始輸出 */}
          {log.outputText && (
            <div>
              <div className="text-xs text-muted mb-1">AI 原始輸出：</div>
              <pre className="text-xs text-slate-300 bg-bg-hover p-2 rounded overflow-x-auto max-h-60 whitespace-pre-wrap">
                {log.outputText}
              </pre>
            </div>
          )}

          {/* 標準化輸出 */}
          {outputJson && (
            <div>
              <div className="text-xs text-muted mb-1">標準化輸出（JSON）：</div>
              <pre className="text-xs text-slate-300 bg-bg-hover p-2 rounded overflow-x-auto max-h-60">
                {JSON.stringify(outputJson, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** 元數據項 */
function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-muted">{label}</span>
      <span className="text-slate-200 truncate">{value}</span>
    </div>
  );
}
