'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { RotationSignalDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshCw } from 'lucide-react';

const DAY_OPTIONS = [3, 5, 10, 20, 30];

export function RotationHistoryChart() {
  const [days, setDays] = useState(5);

  const key = `/stock/rotation?days=${days}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<RotationSignalDto>(
    key,
    () => api.rotation(days),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );

  const option = useMemo(() => {
    if (!data) return null;

    // 風格輪動柱狀圖
    const styleEntries = Object.entries(data.styleRotation).slice(0, 10);
    const styleNames = styleEntries.map(([k]) => k.replace(/\(.*\)/, ''));
    const styleValues = styleEntries.map(([, v]) => v);

    // 領漲/滯後行業對比
    const leading = (data.leadingIndustries || []).slice(0, 10);
    const lagging = (data.laggingIndustries || []).slice(0, 10);
    const leadingNames = leading.map((d) => d.name.replace(/\(.*\)/, ''));
    const leadingValues = leading.map((d) => d.change);
    const laggingNames = lagging.map((d) => d.name.replace(/\(.*\)/, ''));
    const laggingValues = lagging.map((d) => d.change);

    return {
      title: {
        text: `行業輪動信號（近 ${data.days} 日）`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any[]) => {
          const lines = [params[0].axisValue];
          params.forEach((p) => {
            lines.push(`${p.seriesName}: ${Number(p.value).toFixed(3)}%`);
          });
          return lines.join('<br/>');
        },
      },
      legend: {
        data: ['風格輪動', '領漲行業', '滯後行業'],
        top: 28,
        textStyle: { color: '#94a3b8' },
      },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '20%', containLabel: true },
      xAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v.toFixed(1)}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      yAxis: [
        {
          type: 'category',
          data: [...styleNames, ...leadingNames, ...laggingNames],
          axisLabel: { color: '#94a3b8', fontSize: 10 },
          axisLine: { lineStyle: { color: '#334155' } },
        },
      ],
      series: [
        {
          name: '風格輪動',
          type: 'bar',
          data: styleValues.map((v) => ({
            value: v,
            itemStyle: { color: v >= 0 ? '#ef4444' : '#22c55e' },
          })),
          label: {
            show: true,
            position: 'right',
            color: '#94a3b8',
            fontSize: 10,
            formatter: (p: any) => `${p.value.toFixed(2)}%`,
          },
        },
      ],
    };
  }, [data]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">回溯天數：</span>
        {DAY_OPTIONS.map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-2 py-1 rounded text-xs transition-colors ${
              days === d
                ? 'bg-accent/10 text-accent'
                : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
            }`}
          >
            {d} 日
          </button>
        ))}
        <button
          onClick={() => mutate()}
          className="ml-auto flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-400 hover:text-slate-100 hover:bg-bg-hover"
        >
          <RefreshCw className={`w-3 h-3 ${isValidating ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {data?.summary && (
        <div className="rounded-md border border-border bg-bg-panel p-3 text-sm text-slate-300">
          {data.summary}
        </div>
      )}

      {isLoading && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && option && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[500px]">
          <ReactECharts option={option} style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 領漲/滯後行業對比表 */}
      {!isLoading && !error && data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <h4 className="text-sm font-semibold text-red-400 mb-2">領漲行業（Top 10）</h4>
            <div className="space-y-1 max-h-60 overflow-auto">
              {(data.leadingIndustries || []).slice(0, 10).map((d, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate" title={d.name}>{d.name}</span>
                  <span className="text-red-400 ml-2 flex-shrink-0">{d.change.toFixed(3)}%</span>
                </div>
              ))}
              {(!data.leadingIndustries || data.leadingIndustries.length === 0) && (
                <p className="text-xs text-muted">暫無數據</p>
              )}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <h4 className="text-sm font-semibold text-green-400 mb-2">滯後行業（Bottom 10）</h4>
            <div className="space-y-1 max-h-60 overflow-auto">
              {(data.laggingIndustries || []).slice(0, 10).map((d, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate" title={d.name}>{d.name}</span>
                  <span className="text-green-400 ml-2 flex-shrink-0">{d.change.toFixed(3)}%</span>
                </div>
              ))}
              {(!data.laggingIndustries || data.laggingIndustries.length === 0) && (
                <p className="text-xs text-muted">暫無數據</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
