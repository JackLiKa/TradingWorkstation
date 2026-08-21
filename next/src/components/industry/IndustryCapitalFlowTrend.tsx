'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { IndustryDailyDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';

const TOP_N_OPTIONS = [5, 8, 10, 15];

interface Props {
  rangeStart: string;
  rangeEnd: string;
}

export function IndustryCapitalFlowTrend({ rangeStart, rangeEnd }: Props) {
  const [topN, setTopN] = useState(8);

  const key = `/stock/industry-daily/all-range?start=${rangeStart}&end=${rangeEnd}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<IndustryDailyDto[]>(
    key,
    () => api.allIndustryDailyRange(rangeStart, rangeEnd),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );

  const canRender = useDelayedRender(isLoading);

  const option = useMemo(() => {
    if (!data || data.length === 0) return null;

    // 1. 按行業分組，構建每個行業的日期 -> totalAmount 映射
    const industryMap = new Map<string, Map<string, number>>();
    const allDates = new Set<string>();
    for (const item of data) {
      if (item.totalAmount == null) continue;
      if (!industryMap.has(item.industry)) {
        industryMap.set(item.industry, new Map());
      }
      industryMap.get(item.industry)!.set(item.tradeDate, item.totalAmount);
      allDates.add(item.tradeDate);
    }

    // 2. 計算每個行業的區間總成交金額，取 Top N
    const industryTotals = Array.from(industryMap.entries()).map(([ind, series]) => {
      const total = Array.from(series.values()).reduce((s, v) => s + v, 0);
      return { industry: ind, total, series };
    });
    industryTotals.sort((a, b) => b.total - a.total);
    const selected = industryTotals.slice(0, topN);

    // 3. 排序日期
    const sortedDates = Array.from(allDates).sort();

    // 4. 構建每個行業的時間序列
    const colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#a855f7', '#14b8a6', '#eab308', '#6366f1', '#10b981', '#d946ef'];
    const series = selected.map((s, i) => ({
      name: s.industry.replace(/[A-Z]\d+/, '').trim() || s.industry,
      type: 'line',
      data: sortedDates.map((d) => {
        const v = s.series.get(d);
        return v != null ? Number((v / 1e8).toFixed(2)) : null; // 轉為億元
      }),
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      itemStyle: { color: colors[i % colors.length] },
      lineStyle: { width: 2 },
      connectNulls: true,
    }));

    return {
      title: {
        text: `行業資金流向歷史趨勢（Top ${selected.length}，單位：億元）`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any[]) => {
          const date = params[0].axisValue;
          const lines = [date];
          let total = 0;
          params.forEach((p) => {
            if (p.value != null) {
              lines.push(`${p.seriesName}: ${p.value} 億`);
              total += p.value;
            }
          });
          lines.push(`---`);
          lines.push(`合計: ${total.toFixed(2)} 億`);
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
        data: sortedDates,
        axisLabel: { color: '#94a3b8' },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '成交金額(億元)',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, bottom: 5 },
      ],
      series,
    };
  }, [data, topN]);

  // 計算資金流入/流出摘要
  const flowSummary = useMemo(() => {
    if (!data || data.length === 0) return null;

    // 按行業分組，計算區間內淨流入（用 avgPctChg 正負判斷流入/流出）
    const industryMap = new Map<string, { totalAmount: number; avgPctSum: number; days: number }>();
    for (const item of data) {
      if (!industryMap.has(item.industry)) {
        industryMap.set(item.industry, { totalAmount: 0, avgPctSum: 0, days: 0 });
      }
      const entry = industryMap.get(item.industry)!;
      entry.totalAmount += item.totalAmount ?? 0;
      entry.avgPctSum += item.avgPctChg ?? 0;
      entry.days += 1;
    }

    // 計算淨流入指標：avgPctChg 均值 × 成交金額
    const flowList = Array.from(industryMap.entries()).map(([ind, v]) => {
      const avgPct = v.days > 0 ? v.avgPctSum / v.days : 0;
      const netFlow = avgPct * (v.totalAmount / 1e8); // 億元 × % = 淨流入指標
      return { industry: ind, netFlow, avgPct, totalAmount: v.totalAmount / 1e8 };
    });

    const inflow = flowList.filter((f) => f.netFlow > 0).sort((a, b) => b.netFlow - a.netFlow);
    const outflow = flowList.filter((f) => f.netFlow < 0).sort((a, b) => a.netFlow - b.netFlow);

    return {
      inflow: inflow.slice(0, 5),
      outflow: outflow.slice(0, 5),
    };
  }, [data]);

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
        <RefreshButton
          onClick={() => mutate()}
          isLoading={isValidating}
          className="ml-auto"
        />
      </div>

      {(isLoading || !canRender) && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && canRender && option && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[500px]">
          <ReactECharts option={option} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 資金流入/流出摘要 */}
      {flowSummary && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <h4 className="text-sm font-semibold text-red-400 mb-2">資金淨流入 Top 5</h4>
            <div className="space-y-1">
              {flowSummary.inflow.map((f, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate" title={f.industry}>{f.industry}</span>
                  <span className="text-red-400 ml-2 flex-shrink-0">
                    +{f.netFlow.toFixed(2)} · {f.avgPct.toFixed(2)}% · {f.totalAmount.toFixed(1)}億
                  </span>
                </div>
              ))}
              {flowSummary.inflow.length === 0 && <p className="text-xs text-muted">暫無流入數據</p>}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <h4 className="text-sm font-semibold text-green-400 mb-2">資金淨流出 Top 5</h4>
            <div className="space-y-1">
              {flowSummary.outflow.map((f, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate" title={f.industry}>{f.industry}</span>
                  <span className="text-green-400 ml-2 flex-shrink-0">
                    {f.netFlow.toFixed(2)} · {f.avgPct.toFixed(2)}% · {f.totalAmount.toFixed(1)}億
                  </span>
                </div>
              ))}
              {flowSummary.outflow.length === 0 && <p className="text-xs text-muted">暫無流出數據</p>}
            </div>
          </div>
        </div>
      )}
      <p className="text-xs text-muted">
        淨流入指標 = 平均漲跌幅 × 區間總成交金額（億元）。正值表示資金淨流入，負值表示淨流出。
      </p>
    </div>
  );
}
