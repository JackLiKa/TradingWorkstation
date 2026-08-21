'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { IndustryProsperityDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshCw } from 'lucide-react';

const TOP_N_OPTIONS = [5, 8, 10, 15];

interface Props {
  rangeStart: string;
  rangeEnd: string;
}

export function IndustryProsperityTrend({ rangeStart, rangeEnd }: Props) {
  const [topN, setTopN] = useState(8);

  const key = `/stock/industry-prosperity/range?start=${rangeStart}&end=${rangeEnd}&topN=${topN}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<IndustryProsperityDto[]>(
    key,
    () => api.industryProsperityRange(rangeStart, rangeEnd, topN),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );

  // 計算每個行業的景氣度時間序列
  const { trendData, dates, industries, summary } = useMemo(() => {
    if (!data || data.length === 0) {
      return { trendData: [] as IndustryProsperityDto[], dates: [] as string[], industries: [] as string[], summary: null };
    }

    // 按日期分組
    const byDate = new Map<string, IndustryProsperityDto[]>();
    for (const item of data) {
      if (!byDate.has(item.tradeDate)) {
        byDate.set(item.tradeDate, []);
      }
      byDate.get(item.tradeDate)!.push(item);
    }

    const sortedDates = Array.from(byDate.keys()).sort();

    // 取所有日期中出現過的行業（取最後一個日期的 Top N）
    const lastDate = sortedDates[sortedDates.length - 1];
    const lastDateData = byDate.get(lastDate) ?? [];
    const selectedIndustries = lastDateData.map((d) => d.industry);

    // 構建每個行業的景氣度時間序列
    const industrySeriesMap = new Map<string, Map<string, number>>();
    for (const date of sortedDates) {
      const dayData = byDate.get(date) ?? [];
      for (const item of dayData) {
        if (!industrySeriesMap.has(item.industry)) {
          industrySeriesMap.set(item.industry, new Map());
        }
        industrySeriesMap.get(item.industry)!.set(date, item.prosperityIndex);
      }
    }

    // 計算每個行業的景氣度變化趨勢（首日 vs 末日）
    const trendChanges = selectedIndustries.map((ind) => {
      const series = industrySeriesMap.get(ind);
      if (!series) return { industry: ind, change: 0, first: 0, last: 0 };
      const first = series.get(sortedDates[0]) ?? 0;
      const last = series.get(lastDate) ?? 0;
      return { industry: ind, change: last - first, first, last };
    });

    // 統計：上升/下降/穩定行業數
    const rising = trendChanges.filter((t) => t.change > 5).length;
    const falling = trendChanges.filter((t) => t.change < -5).length;
    const stable = trendChanges.length - rising - falling;

    return {
      trendData: data,
      dates: sortedDates,
      industries: selectedIndustries,
      summary: { rising, falling, stable, total: trendChanges.length, trendChanges },
    };
  }, [data]);

  const option = useMemo(() => {
    if (trendData.length === 0 || dates.length === 0 || industries.length === 0) return null;

    // 構建行業 -> 日期 -> 景氣度 映射
    const industryDateMap = new Map<string, Map<string, IndustryProsperityDto>>();
    for (const item of trendData) {
      if (!industryDateMap.has(item.industry)) {
        industryDateMap.set(item.industry, new Map());
      }
      industryDateMap.get(item.industry)!.set(item.tradeDate, item);
    }

    const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#22c55e', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#a855f7', '#14b8a6', '#eab308', '#6366f1', '#10b981', '#d946ef'];

    const series = industries.map((ind, i) => {
      const dateMap = industryDateMap.get(ind) ?? new Map();
      return {
        name: ind.replace(/[A-Z]\d+/, '').trim() || ind,
        type: 'line',
        data: dates.map((d) => {
          const item = dateMap.get(d);
          return item ? item.prosperityIndex : null;
        }),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: { color: colors[i % colors.length] },
        lineStyle: { width: 2 },
        connectNulls: true,
      };
    });

    return {
      title: {
        text: `行業景氣度歷史趨勢（Top ${industries.length}，${dates[0]} ~ ${dates[dates.length - 1]}）`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any[]) => {
          const date = params[0].axisValue;
          const lines = [date];
          params.forEach((p) => {
            if (p.value != null) {
              const grade = p.value >= 80 ? '繁榮' : p.value >= 65 ? '景氣' : p.value >= 50 ? '平穩' : p.value >= 35 ? '低迷' : '衰退';
              lines.push(`${p.seriesName}: ${p.value.toFixed(1)} (${grade})`);
            }
          });
          return lines.join('<br/>');
        },
      },
      legend: {
        top: 28,
        textStyle: { color: '#94a3b8', fontSize: 10 },
        type: 'scroll',
      },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: '#94a3b8' },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '景氣度(0-100)',
        min: 0,
        max: 100,
        axisLabel: { color: '#94a3b8' },
        splitLine: {
          lineStyle: { color: '#1e293b' },
        },
        // 標記等級區間
        axisLine: { show: false },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, bottom: 5 },
      ],
      series,
    };
  }, [trendData, dates, industries]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">顯示行業數：</span>
        {TOP_N_OPTIONS.map((n) => (
          <button
            key={n}
            onClick={() => setTopN(n)}
            className={`px-2 py-1 rounded text-xs transition-colors ${
              topN === n
                ? 'bg-accent/10 text-accent'
                : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
            }`}
          >
            Top {n}
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

      {/* 趨勢統計摘要 */}
      {summary && (
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="rounded border border-border bg-bg-panel p-2 text-center">
            <div className="text-muted">景氣度上升</div>
            <div className="text-lg font-bold text-red-400">{summary.rising}</div>
          </div>
          <div className="rounded border border-border bg-bg-panel p-2 text-center">
            <div className="text-muted">景氣度穩定</div>
            <div className="text-lg font-bold text-blue-400">{summary.stable}</div>
          </div>
          <div className="rounded border border-border bg-bg-panel p-2 text-center">
            <div className="text-muted">景氣度下降</div>
            <div className="text-lg font-bold text-green-400">{summary.falling}</div>
          </div>
        </div>
      )}

      {isLoading && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && option && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[500px]">
          <ReactECharts option={option} style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 景氣度變化排行 */}
      {summary && summary.trendChanges.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <h4 className="text-sm font-semibold text-red-400 mb-2">景氣度上升 Top 5</h4>
            <div className="space-y-1">
              {[...summary.trendChanges]
                .sort((a, b) => b.change - a.change)
                .slice(0, 5)
                .map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-slate-300 truncate" title={t.industry}>{t.industry}</span>
                    <span className="text-red-400 ml-2 flex-shrink-0">
                      {t.first.toFixed(1)} → {t.last.toFixed(1)} (+{t.change.toFixed(1)})
                    </span>
                  </div>
                ))}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <h4 className="text-sm font-semibold text-green-400 mb-2">景氣度下降 Top 5</h4>
            <div className="space-y-1">
              {[...summary.trendChanges]
                .sort((a, b) => a.change - b.change)
                .slice(0, 5)
                .map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-slate-300 truncate" title={t.industry}>{t.industry}</span>
                    <span className="text-green-400 ml-2 flex-shrink-0">
                      {t.first.toFixed(1)} → {t.last.toFixed(1)} ({t.change.toFixed(1)})
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      <p className="text-xs text-muted">
        景氣度變化 &gt; +5 視為上升，&lt; -5 視為下降，其餘為穩定。趨勢圖展示各行業景氣度隨時間的變化軌跡。
      </p>
    </div>
  );
}
