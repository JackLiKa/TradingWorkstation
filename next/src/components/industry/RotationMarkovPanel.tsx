'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { RotationMarkovDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { GitBranch, ArrowRight, Crown } from 'lucide-react';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';
import { AnalysisTutorial } from '@/components/industry/AnalysisTutorial';

const LOOKBACK_OPTIONS = [15, 30, 60, 90];
const STATE_NAMES = ['領漲', '中間', '滯後'];
const STATE_COLORS = ['#ef4444', '#eab308', '#3b82f6'];

export function RotationMarkovPanel() {
  const [lookbackDays, setLookbackDays] = useState(30);
  const [selectedIndustry, setSelectedIndustry] = useState<string>('');

  const key = `/stock/rotation-markov?lookbackDays=${lookbackDays}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<RotationMarkovDto>(
    key,
    () => api.rotationMarkov(lookbackDays),
    { revalidateOnFocus: false, dedupingInterval: 300_000 }
  );
  const canRender = useDelayedRender(isLoading);

  const industries = useMemo(() => {
    if (!data || !data.industries) return [];
    return Object.keys(data.industries).sort();
  }, [data]);

  useMemo(() => {
    if (industries.length > 0 && !selectedIndustry) {
      setSelectedIndustry(industries[0]);
    }
  }, [industries, selectedIndustry]);

  // 長期領漲概率排行
  const leaderRanking = useMemo(() => {
    if (!data || !data.industries) return [];
    return Object.values(data.industries)
      .sort((a, b) => b.leaderProbability - a.leaderProbability)
      .slice(0, 15);
  }, [data]);

  // 轉移矩陣熱力圖
  const matrixOption = useMemo(() => {
    if (!data || !selectedIndustry || !data.industries[selectedIndustry]) return null;
    const markov = data.industries[selectedIndustry];
    const matrix = markov.transitionMatrix;

    const heatmapData: [number, number, number][] = [];
    for (let i = 0; i < 3; i++) {
      for (let j = 0; j < 3; j++) {
        heatmapData.push([j, i, matrix[i][j]]);
      }
    }

    return {
      title: {
        text: `${selectedIndustry} — 輪動狀態轉移矩陣`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const from = STATE_NAMES[params.value[1]];
          const to = STATE_NAMES[params.value[0]];
          const prob = (params.value[2] * 100).toFixed(1);
          return `從「${from}」到「${to}」<br/>概率: ${prob}%`;
        },
      },
      grid: { left: '12%', right: '5%', bottom: '15%', top: '15%' },
      xAxis: {
        type: 'category',
        data: STATE_NAMES,
        name: '轉移至',
        nameLocation: 'middle',
        nameGap: 30,
        axisLabel: { color: '#94a3b8' },
        splitArea: { show: true },
      },
      yAxis: {
        type: 'category',
        data: STATE_NAMES,
        name: '當前狀態',
        axisLabel: { color: '#94a3b8' },
        splitArea: { show: true },
      },
      visualMap: {
        min: 0,
        max: 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '2%',
        textStyle: { color: '#94a3b8' },
        inRange: { color: ['#1e293b', '#3b82f6', '#22c55e', '#eab308', '#ef4444'] },
      },
      series: [
        {
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: true,
            color: '#fff',
            fontSize: 12,
            formatter: (p: any) => `${(p.value[2] * 100).toFixed(0)}%`,
          },
        },
      ],
    };
  }, [data, selectedIndustry]);

  // 下一期狀態概率 + 穩態分布
  const probOption = useMemo(() => {
    if (!data || !selectedIndustry || !data.industries[selectedIndustry]) return null;
    const markov = data.industries[selectedIndustry];

    const nextData = STATE_NAMES.map((name, i) => ({
      value: (markov.nextProbabilities[i + 1] ?? 0) * 100,
      itemStyle: { color: STATE_COLORS[i] },
    }));
    const steadyData = STATE_NAMES.map((name, i) => ({
      value: (markov.steadyState[i + 1] ?? 0) * 100,
      itemStyle: { color: STATE_COLORS[i] },
    }));

    return {
      title: {
        text: '下一期概率 vs 穩態分布',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          return params.map((p) => `${p.seriesName}: ${p.value.toFixed(1)}%`).join('<br/>');
        },
      },
      legend: {
        data: ['下一期概率', '穩態分布'],
        top: 28,
        textStyle: { color: '#94a3b8', fontSize: 10 },
      },
      grid: { left: '5%', right: '5%', bottom: '10%', top: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: STATE_NAMES,
        axisLabel: { color: '#94a3b8' },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '概率(%)',
        max: 100,
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      series: [
        {
          name: '下一期概率',
          type: 'bar',
          data: nextData,
          label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: (p: any) => `${p.value.toFixed(1)}%` },
        },
        {
          name: '穩態分布',
          type: 'bar',
          data: steadyData,
          label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: (p: any) => `${p.value.toFixed(1)}%` },
        },
      ],
    };
  }, [data, selectedIndustry]);

  // 長期領漲概率排行圖
  const rankingOption = useMemo(() => {
    if (leaderRanking.length === 0) return null;

    return {
      title: {
        text: '長期領漲概率排行 Top 15',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          const p = params[0];
          const m = leaderRanking[p.dataIndex];
          return `${p.name}<br/>領漲概率: ${(p.value * 100).toFixed(1)}%<br/>當前狀態: ${m.currentStateName}<br/>最可能下一狀態: ${m.mostLikelyNext}`;
        },
      },
      grid: { left: '3%', right: '5%', bottom: '5%', top: '15%', containLabel: true },
      xAxis: {
        type: 'value',
        name: '領漲概率',
        max: 1,
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      yAxis: {
        type: 'category',
        data: leaderRanking.map((m) => m.industry).reverse(),
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      series: [
        {
          type: 'bar',
          data: leaderRanking.map((m) => m.leaderProbability).reverse(),
          itemStyle: {
            color: (p: any) => {
              const v = p.value;
              if (v >= 0.5) return '#ef4444';
              if (v >= 0.4) return '#f97316';
              if (v >= 0.34) return '#eab308';
              return '#3b82f6';
            },
          },
          label: {
            show: true,
            position: 'right',
            color: '#94a3b8',
            fontSize: 10,
            formatter: (p: any) => `${(p.value * 100).toFixed(1)}%`,
          },
        },
      ],
    };
  }, [leaderRanking]);

  return (
    <div className="space-y-3">
      <AnalysisTutorial tutorialKey="rotationMarkov" />
      {/* 參數選擇器 */}
      <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-bg-panel p-3">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-accent" />
          <span className="text-sm text-muted">輪動 Markov 模型</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">回溯天數：</span>
          {LOOKBACK_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setLookbackDays(d)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                lookbackDays === d ? 'bg-accent/10 text-accent' : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
              }`}
            >
              {d}日
            </button>
          ))}
        </div>
        <RefreshButton
          onClick={() => mutate()}
          isLoading={isValidating}
          className="ml-auto"
        />
      </div>

      {/* 摘要 */}
      {data && (
        <div className="rounded-md border border-border bg-bg-panel p-3 text-sm text-slate-300">
          {data.summary}
        </div>
      )}

      {(isLoading || !canRender) && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}

      {/* 長期領漲概率排行 */}
      {!isLoading && !error && canRender && rankingOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[450px]">
          <ReactECharts option={rankingOption} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 行業選擇器 */}
      {!isLoading && !error && industries.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-bg-panel p-3">
          <span className="text-sm text-muted">選擇行業：</span>
          <select
            value={selectedIndustry}
            onChange={(e) => setSelectedIndustry(e.target.value)}
            className="bg-bg-panel text-sm text-slate-100 rounded border border-border px-3 py-1.5 outline-none min-w-[200px]"
          >
            {industries.map((ind) => (
              <option key={ind} value={ind}>
                {ind}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* 當前狀態 + 預測摘要 */}
      {!isLoading && !error && data && selectedIndustry && data.industries[selectedIndustry] && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted mb-1">當前狀態</p>
            <p className="text-lg font-semibold text-slate-100">
              {data.industries[selectedIndustry].currentStateName}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted mb-1">最可能下一狀態</p>
            <div className="flex items-center gap-1">
              <span className="text-lg font-semibold text-accent">
                {data.industries[selectedIndustry].mostLikelyNext}
              </span>
              <ArrowRight className="w-3 h-3 text-muted" />
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted mb-1">轉換概率</p>
            <p className="text-lg font-semibold text-accent">
              {(data.industries[selectedIndustry].mostLikelyNextProb * 100).toFixed(1)}%
            </p>
          </div>
          <div className="rounded-lg border border-accent/30 bg-accent/5 p-3">
            <div className="flex items-center gap-2 mb-1">
              <Crown className="w-4 h-4 text-accent" />
              <p className="text-xs text-muted">長期領漲概率</p>
            </div>
            <p className="text-lg font-semibold text-accent">
              {(data.industries[selectedIndustry].leaderProbability * 100).toFixed(1)}%
            </p>
          </div>
        </div>
      )}

      {/* 轉移矩陣熱力圖 */}
      {!isLoading && !error && canRender && matrixOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[350px]">
          <ReactECharts option={matrixOption} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 下一期概率 + 穩態分布 */}
      {!isLoading && !error && canRender && probOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[300px]">
          <ReactECharts option={probOption} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      <p className="text-xs text-muted">
        輪動 Markov 模型：將行業按每日漲跌幅排名分為 3 個狀態（領漲/中間/滯後），
        基於歷史狀態轉換構建轉移矩陣。長期領漲概率 &gt; 40% 表示該行業有較強的輪動領漲慣性，
        可作為輪動策略的候選標的。
      </p>
    </div>
  );
}
