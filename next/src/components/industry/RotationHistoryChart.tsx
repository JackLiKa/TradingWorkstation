'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { RotationSignalDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshCw, TrendingUp } from 'lucide-react';

const DAY_OPTIONS = [3, 5, 10, 20, 30];

/** 多日輪動趨勢數據 */
interface MultiDayRotation {
  dayWindows: number[];
  styleTrends: Record<string, number[]>; // styleName -> [val@3d, val@5d, ...]
  topIndustryTrends: { name: string; values: number[] }[];
}

export function RotationHistoryChart() {
  const [days, setDays] = useState(5);
  const [showTrend, setShowTrend] = useState(false);

  // 單日輪動數據
  const key = `/stock/rotation?days=${days}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<RotationSignalDto>(
    key,
    () => api.rotation(days),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );

  // 多日對比數據（用於趨勢線）
  const trendKey = showTrend ? 'rotation-multi-day-trend' : null;
  const { data: multiDayData, isLoading: trendLoading } = useSWR<MultiDayRotation>(
    trendKey,
    async () => {
      const results = await Promise.all(DAY_OPTIONS.map((d) => api.rotation(d)));
      const dayWindows = DAY_OPTIONS;
      // 收集所有風格指數名稱
      const styleNames = new Set<string>();
      results.forEach((r) => {
        Object.keys(r.styleRotation || {}).forEach((k) => styleNames.add(k));
      });
      // 構建每個風格的趨勢數據
      const styleTrends: Record<string, number[]> = {};
      styleNames.forEach((name) => {
        styleTrends[name] = results.map((r) => r.styleRotation?.[name] ?? 0);
      });
      // 收集領漲行業（取所有天數窗口的並集 Top 8）
      const industryMap = new Map<string, number[]>();
      results.forEach((r, idx) => {
        (r.leadingIndustries || []).slice(0, 10).forEach((ind) => {
          if (!industryMap.has(ind.name)) industryMap.set(ind.name, new Array(DAY_OPTIONS.length).fill(0));
          industryMap.get(ind.name)![idx] = ind.change;
        });
      });
      // 取出現次數最多的前 8 個行業
      const topIndustryTrends = Array.from(industryMap.entries())
        .map(([name, values]) => ({ name, values }))
        .sort((a, b) => b.values.reduce((s, v) => s + v, 0) - a.values.reduce((s, v) => s + v, 0))
        .slice(0, 8);

      return { dayWindows, styleTrends, topIndustryTrends };
    },
    { revalidateOnFocus: false, dedupingInterval: 300_000 }
  );

  // 單日柱狀圖 option
  const barOption = useMemo(() => {
    if (!data) return null;

    const styleEntries = Object.entries(data.styleRotation).slice(0, 10);
    const styleNames = styleEntries.map(([k]) => k.replace(/\(.*\)/, ''));
    const styleValues = styleEntries.map(([, v]) => v);

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
      grid: { left: '3%', right: '4%', bottom: '15%', top: '15%', containLabel: true },
      xAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v.toFixed(1)}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      yAxis: {
        type: 'category',
        data: styleNames,
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
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

  // 多日趨勢線 option
  const trendOption = useMemo(() => {
    if (!multiDayData) return null;

    const { dayWindows, styleTrends, topIndustryTrends } = multiDayData;
    const colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16'];

    const styleSeries = Object.entries(styleTrends).slice(0, 6).map(([name, values], i) => ({
      name: name.replace(/\(.*\)/, ''),
      type: 'line',
      data: values,
      smooth: true,
      itemStyle: { color: colors[i % colors.length] },
      lineStyle: { width: 2 },
      symbol: 'circle',
      symbolSize: 6,
    }));

    const industrySeries = topIndustryTrends.map((ind, i) => ({
      name: ind.name.replace(/\(.*\)/, ''),
      type: 'line',
      data: ind.values,
      smooth: true,
      itemStyle: { color: colors[(i + 6) % colors.length] },
      lineStyle: { width: 1.5, type: 'dashed' as const },
      symbol: 'diamond',
      symbolSize: 5,
    }));

    return {
      title: {
        text: '多日輪動趨勢對比',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          const window = params[0].axisValue;
          const lines = [`回溯 ${window} 日`];
          params.forEach((p) => {
            lines.push(`${p.seriesName}: ${Number(p.value).toFixed(3)}%`);
          });
          return lines.join('<br/>');
        },
      },
      legend: {
        top: 28,
        textStyle: { color: '#94a3b8', fontSize: 10 },
        type: 'scroll',
      },
      grid: { left: '3%', right: '4%', bottom: '12%', top: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: dayWindows.map((d) => `${d} 日`),
        axisLabel: { color: '#94a3b8' },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '漲跌幅(%)',
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v.toFixed(1)}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      series: [...styleSeries, ...industrySeries],
    };
  }, [multiDayData]);

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
          onClick={() => setShowTrend((v) => !v)}
          className={`ml-auto flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
            showTrend
              ? 'bg-accent/10 text-accent'
              : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
          }`}
        >
          <TrendingUp className="w-3 h-3" />
          {showTrend ? '隱藏趨勢對比' : '顯示趨勢對比'}
        </button>
        <button
          onClick={() => mutate()}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-400 hover:text-slate-100 hover:bg-bg-hover"
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

      {/* 多日趨勢對比圖 */}
      {showTrend && (
        <>
          {trendLoading && <ChartSkeleton />}
          {!trendLoading && trendOption && (
            <div className="rounded-lg border border-border bg-bg-panel p-4 h-[450px]">
              <ReactECharts option={trendOption} style={{ width: '100%', height: '100%' }} />
            </div>
          )}
          <p className="text-xs text-muted">
            實線 = 風格指數輪動趨勢，虛線 = 領漲行業輪動趨勢。橫軸為回溯天數窗口，縱軸為對應區間漲跌幅。
          </p>
        </>
      )}

      {/* 單日柱狀圖 */}
      {isLoading && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && barOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[400px]">
          <ReactECharts option={barOption} style={{ width: '100%', height: '100%' }} />
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
