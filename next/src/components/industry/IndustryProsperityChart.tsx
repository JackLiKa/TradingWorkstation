'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { IndustryProsperityDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshCw, TrendingUp, TrendingDown, Minus } from 'lucide-react';

const GRADE_COLORS: Record<string, string> = {
  '繁榮': '#ef4444',
  '景氣': '#f59e0b',
  '平穩': '#3b82f6',
  '低迷': '#64748b',
  '衰退': '#22c55e',
};

const GRADE_BG: Record<string, string> = {
  '繁榮': 'bg-red-500/15 text-red-400 border-red-500/25',
  '景氣': 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  '平穩': 'bg-blue-500/15 text-blue-400 border-blue-500/25',
  '低迷': 'bg-slate-500/15 text-slate-400 border-slate-500/25',
  '衰退': 'bg-green-500/15 text-green-400 border-green-500/25',
};

export function IndustryProsperityChart() {
  const key = '/stock/industry-prosperity';
  const { data, error, isLoading, mutate, isValidating } = useSWR<IndustryProsperityDto[]>(
    key,
    () => api.industryProsperity(),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );

  const option = useMemo(() => {
    if (!data || data.length === 0) return null;

    // 取 Top 20 行業
    const top = data.slice(0, 20);
    const industries = top.map((d) => d.industry.replace(/[A-Z]\d+/, '').trim() || d.industry);
    const prosperityValues = top.map((d) => d.prosperityIndex);
    const momentumValues = top.map((d) => d.momentumScore);
    const capitalValues = top.map((d) => d.capitalScore);
    const activityValues = top.map((d) => d.activityScore);
    const breadthValues = top.map((d) => d.breadthScore);

    return {
      title: {
        text: `行業景氣度排行（Top 20，${data[0]?.tradeDate ?? ''}）`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any[]) => {
          const idx = params[0].dataIndex;
          const d = top[idx];
          const lines = [d.industry];
          lines.push(`綜合景氣度: ${d.prosperityIndex.toFixed(1)} (${d.grade})`);
          lines.push(`--- 分項評分 ---`);
          lines.push(`動量(漲跌幅): ${d.momentumScore.toFixed(1)}`);
          lines.push(`資金(成交額): ${d.capitalScore.toFixed(1)}`);
          lines.push(`活躍(換手率): ${d.activityScore.toFixed(1)}`);
          lines.push(`廣度(漲跌比): ${d.breadthScore.toFixed(1)}`);
          lines.push(`--- 原始數據 ---`);
          lines.push(`漲跌幅: ${d.avgPctChg?.toFixed(3) ?? 'N/A'}%`);
          lines.push(`成交額: ${(d.totalAmount ?? 0).toFixed(0)}`);
          lines.push(`換手率: ${d.avgTurn?.toFixed(3) ?? 'N/A'}%`);
          lines.push(`上漲/下跌: ${d.risingCount ?? 0}/${d.fallingCount ?? 0}`);
          return lines.join('<br/>');
        },
      },
      legend: {
        data: ['綜合景氣度', '動量', '資金', '活躍', '廣度'],
        top: 28,
        textStyle: { color: '#94a3b8', fontSize: 10 },
      },
      grid: { left: '3%', right: '4%', bottom: '25%', top: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: industries,
        axisLabel: { rotate: 45, color: '#94a3b8', fontSize: 10, interval: 0 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '評分(0-100)',
        min: 0,
        max: 100,
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      series: [
        {
          name: '綜合景氣度',
          type: 'bar',
          data: prosperityValues.map((v) => ({
            value: v,
            itemStyle: {
              color: v >= 80 ? '#ef4444' : v >= 65 ? '#f59e0b' : v >= 50 ? '#3b82f6' : v >= 35 ? '#64748b' : '#22c55e',
            },
          })),
          label: {
            show: true,
            position: 'top',
            color: '#94a3b8',
            fontSize: 9,
            formatter: (p: any) => p.value.toFixed(0),
          },
        },
        {
          name: '動量',
          type: 'line',
          data: momentumValues,
          smooth: true,
          itemStyle: { color: '#ef4444' },
          lineStyle: { width: 1.5 },
          symbol: 'circle',
          symbolSize: 4,
        },
        {
          name: '資金',
          type: 'line',
          data: capitalValues,
          smooth: true,
          itemStyle: { color: '#f59e0b' },
          lineStyle: { width: 1.5 },
          symbol: 'circle',
          symbolSize: 4,
        },
        {
          name: '活躍',
          type: 'line',
          data: activityValues,
          smooth: true,
          itemStyle: { color: '#8b5cf6' },
          lineStyle: { width: 1.5 },
          symbol: 'circle',
          symbolSize: 4,
        },
        {
          name: '廣度',
          type: 'line',
          data: breadthValues,
          smooth: true,
          itemStyle: { color: '#22c55e' },
          lineStyle: { width: 1.5 },
          symbol: 'circle',
          symbolSize: 4,
        },
      ],
    };
  }, [data]);

  // 統計摘要
  const summary = useMemo(() => {
    if (!data || data.length === 0) return null;
    const grades: Record<string, number> = { '繁榮': 0, '景氣': 0, '平穩': 0, '低迷': 0, '衰退': 0 };
    let totalIndex = 0;
    for (const d of data) {
      grades[d.grade] = (grades[d.grade] ?? 0) + 1;
      totalIndex += d.prosperityIndex;
    }
    return {
      grades,
      avgIndex: totalIndex / data.length,
      total: data.length,
    };
  }, [data]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button
          onClick={() => mutate()}
          className="ml-auto flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-400 hover:text-slate-100 hover:bg-bg-hover"
        >
          <RefreshCw className={`w-3 h-3 ${isValidating ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {/* 景氣度分佈摘要 */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
          <div className="rounded border border-border bg-bg-panel p-2 text-center">
            <div className="text-xs text-muted">平均景氣度</div>
            <div className="text-lg font-bold text-fg">{summary.avgIndex.toFixed(1)}</div>
          </div>
          {Object.entries(summary.grades).map(([grade, count]) => (
            <div key={grade} className={`rounded border p-2 text-center ${GRADE_BG[grade] ?? 'border-border bg-bg-panel'}`}>
              <div className="text-xs opacity-80">{grade}</div>
              <div className="text-lg font-bold">{count}</div>
            </div>
          ))}
        </div>
      )}

      {isLoading && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && option && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[550px]">
          <ReactECharts option={option} style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 景氣度排行表 */}
      {!isLoading && !error && data && (
        <div className="rounded-lg border border-border bg-bg-panel p-3">
          <h4 className="text-sm font-semibold text-slate-100 mb-2">行業景氣度排行（Top 15）</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-border">
                  <th className="text-left py-1 px-2">排名</th>
                  <th className="text-left py-1 px-2">行業</th>
                  <th className="text-right py-1 px-2">景氣度</th>
                  <th className="text-center py-1 px-2">等級</th>
                  <th className="text-right py-1 px-2">動量</th>
                  <th className="text-right py-1 px-2">資金</th>
                  <th className="text-right py-1 px-2">活躍</th>
                  <th className="text-right py-1 px-2">廣度</th>
                  <th className="text-right py-1 px-2">漲跌幅</th>
                </tr>
              </thead>
              <tbody>
                {data.slice(0, 15).map((d, i) => (
                  <tr key={d.industry} className="border-b border-border/50 hover:bg-bg-hover/30">
                    <td className="py-1 px-2 text-muted">{i + 1}</td>
                    <td className="py-1 px-2 text-slate-300 truncate max-w-[200px]" title={d.industry}>{d.industry}</td>
                    <td className="py-1 px-2 text-right font-medium" style={{ color: GRADE_COLORS[d.grade] ?? '#e2e8f0' }}>
                      {d.prosperityIndex.toFixed(1)}
                    </td>
                    <td className="py-1 px-2 text-center">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${GRADE_BG[d.grade] ?? ''}`}>
                        {d.grade}
                      </span>
                    </td>
                    <td className="py-1 px-2 text-right text-slate-400">{d.momentumScore.toFixed(1)}</td>
                    <td className="py-1 px-2 text-right text-slate-400">{d.capitalScore.toFixed(1)}</td>
                    <td className="py-1 px-2 text-right text-slate-400">{d.activityScore.toFixed(1)}</td>
                    <td className="py-1 px-2 text-right text-slate-400">{d.breadthScore.toFixed(1)}</td>
                    <td className={`py-1 px-2 text-right ${(d.avgPctChg ?? 0) >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {(d.avgPctChg ?? 0).toFixed(3)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-muted">
        景氣度 = 動量(35%) + 資金(25%) + 活躍(20%) + 廣度(20%)。各維度標準化到 0-100，加權綜合。
      </p>
    </div>
  );
}
