'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { RotationAutoMlDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshCw, Zap, Award, Target } from 'lucide-react';

const BACKTEST_OPTIONS = [60, 90, 180];

export function RotationAutoMlPanel() {
  const [backtestDays, setBacktestDays] = useState(90);

  const key = `/stock/rotation-prediction/automl?backtestDays=${backtestDays}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<RotationAutoMlDto>(
    key,
    () => api.rotationAutoMl(backtestDays),
    { revalidateOnFocus: false, dedupingInterval: 300_000 }
  );

  // 參數組合熱力圖（lookback × forward → compositeScore）
  const heatmapOption = useMemo(() => {
    if (!data || !data.combinations || data.combinations.length === 0) return null;

    const lookbacks = [...new Set(data.combinations.map((c) => c.lookbackDays))].sort((a, b) => a - b);
    const forwards = [...new Set(data.combinations.map((c) => c.forwardDays))].sort((a, b) => a - b);

    const heatmapData: [number, number, number][] = [];
    for (let i = 0; i < lookbacks.length; i++) {
      for (let j = 0; j < forwards.length; j++) {
        const combo = data.combinations.find(
          (c) => c.lookbackDays === lookbacks[i] && c.forwardDays === forwards[j]
        );
        if (combo) {
          heatmapData.push([j, i, combo.compositeScore]);
        }
      }
    }

    return {
      title: {
        text: '參數組合綜合評分熱力圖',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const lookback = lookbacks[params.value[1]];
          const forward = forwards[params.value[0]];
          const combo = data.combinations.find(
            (c) => c.lookbackDays === lookback && c.forwardDays === forward
          );
          if (!combo) return '';
          const lines = [
            `lookback=${lookback}日, forward=${forward}日`,
            `綜合評分: ${combo.compositeScore.toFixed(1)}`,
            `命中率: ${combo.hitRate.toFixed(1)}%`,
            `超額收益: ${combo.avgExcessReturn.toFixed(3)}%`,
            `預測領漲收益: ${combo.avgLeaderReturn.toFixed(3)}%`,
            `回測次數: ${combo.totalPredictions}`,
          ];
          return lines.join('<br/>');
        },
      },
      grid: { left: '8%', right: '5%', bottom: '10%', top: '15%' },
      xAxis: {
        type: 'category',
        data: forwards.map((f) => `${f}日`),
        name: 'forwardDays',
        nameLocation: 'middle',
        nameGap: 25,
        axisLabel: { color: '#94a3b8' },
        splitArea: { show: true },
      },
      yAxis: {
        type: 'category',
        data: lookbacks.map((l) => `${l}日`),
        name: 'lookbackDays',
        axisLabel: { color: '#94a3b8' },
        splitArea: { show: true },
      },
      visualMap: {
        min: 0,
        max: 100,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '2%',
        textStyle: { color: '#94a3b8' },
        inRange: { color: ['#1e40af', '#3b82f6', '#22c55e', '#eab308', '#ef4444'] },
      },
      series: [
        {
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: true,
            color: '#fff',
            fontSize: 11,
            formatter: (p: any) => p.value[2].toFixed(1),
          },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
          },
        },
      ],
    };
  }, [data]);

  // 超額收益 vs 命中率散點圖
  const scatterOption = useMemo(() => {
    if (!data || !data.combinations || data.combinations.length === 0) return null;

    const scatterData = data.combinations.map((c) => ({
      value: [c.hitRate, c.avgExcessReturn, c.compositeScore],
      name: `L${c.lookbackDays}F${c.forwardDays}`,
    }));

    return {
      title: {
        text: '命中率 vs 超額收益（每組參數一點）',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        formatter: (params: any) => {
          return `${params.name}<br/>命中率: ${params.value[0].toFixed(1)}%<br/>超額收益: ${params.value[1].toFixed(3)}%<br/>綜合評分: ${params.value[2].toFixed(1)}`;
        },
      },
      grid: { left: '8%', right: '5%', bottom: '12%', top: '15%' },
      xAxis: {
        type: 'value',
        name: '命中率(%)',
        min: 0,
        max: 100,
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      yAxis: {
        type: 'value',
        name: '超額收益(%)',
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      series: [
        {
          type: 'scatter',
          data: scatterData,
          symbolSize: (val: number[]) => Math.max(12, val[2] / 3),
          label: {
            show: true,
            formatter: (p: any) => p.name,
            color: '#e2e8f0',
            fontSize: 10,
            position: 'right',
          },
          itemStyle: {
            color: (p: any) => {
              const score = p.value[2];
              if (score >= 70) return '#ef4444';
              if (score >= 50) return '#eab308';
              return '#64748b';
            },
          },
        },
      ],
    };
  }, [data]);

  return (
    <div className="space-y-3">
      {/* 參數選擇器 */}
      <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-bg-panel p-3">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-accent" />
          <span className="text-sm text-muted">AutoML 自動調參</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">回測區間：</span>
          {BACKTEST_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setBacktestDays(d)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                backtestDays === d ? 'bg-accent/10 text-accent' : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
              }`}
            >
              {d}日
            </button>
          ))}
        </div>
        <button
          onClick={() => mutate()}
          className="ml-auto flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-400 hover:text-slate-100 hover:bg-bg-hover"
        >
          <RefreshCw className={`w-3 h-3 ${isValidating ? 'animate-spin' : ''}`} />
          重新調參
        </button>
      </div>

      {/* 最佳參數卡片 */}
      {data && data.bestLookbackDays > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-lg border border-accent/30 bg-accent/5 p-3">
            <div className="flex items-center gap-2 mb-1">
              <Award className="w-4 h-4 text-accent" />
              <p className="text-xs text-muted">最佳 lookback</p>
            </div>
            <p className="text-lg font-semibold text-accent">{data.bestLookbackDays} 日</p>
          </div>
          <div className="rounded-lg border border-accent/30 bg-accent/5 p-3">
            <div className="flex items-center gap-2 mb-1">
              <Target className="w-4 h-4 text-accent" />
              <p className="text-xs text-muted">最佳 forward</p>
            </div>
            <p className="text-lg font-semibold text-accent">{data.bestForwardDays} 日</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted mb-1">最佳命中率</p>
            <p className="text-lg font-semibold text-red-400">{data.bestHitRate.toFixed(1)}%</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted mb-1">最佳超額收益</p>
            <p className={`text-lg font-semibold ${data.bestExcessReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
              {data.bestExcessReturn >= 0 ? '+' : ''}{data.bestExcessReturn.toFixed(3)}%
            </p>
          </div>
        </div>
      )}

      {/* 摘要 */}
      {data && (
        <div className="rounded-md border border-border bg-bg-panel p-3 text-sm text-slate-300">
          {data.summary}
        </div>
      )}

      {isLoading && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}

      {/* 參數組合熱力圖 */}
      {!isLoading && !error && heatmapOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[400px]">
          <ReactECharts option={heatmapOption} style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 散點圖 */}
      {!isLoading && !error && scatterOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[400px]">
          <ReactECharts option={scatterOption} style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 參數組合明細表 */}
      {!isLoading && !error && data && data.combinations.length > 0 && (
        <div className="rounded-lg border border-border bg-bg-panel p-4">
          <h4 className="text-sm font-semibold text-slate-100 mb-3">參數組合明細（按綜合評分倒序）</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-muted">
                  <th className="text-left py-2 px-2">lookback</th>
                  <th className="text-left py-2 px-2">forward</th>
                  <th className="text-right py-2 px-2">命中率</th>
                  <th className="text-right py-2 px-2">超額收益</th>
                  <th className="text-right py-2 px-2">領漲收益</th>
                  <th className="text-right py-2 px-2">回測次數</th>
                  <th className="text-right py-2 px-2">綜合評分</th>
                </tr>
              </thead>
              <tbody>
                {data.combinations.map((c, i) => (
                  <tr
                    key={`${c.lookbackDays}-${c.forwardDays}`}
                    className={`border-b border-border/30 hover:bg-bg-hover/30 ${
                      i === 0 ? 'bg-accent/5' : ''
                    }`}
                  >
                    <td className="py-1.5 px-2 text-slate-300">{c.lookbackDays}日</td>
                    <td className="py-1.5 px-2 text-slate-300">{c.forwardDays}日</td>
                    <td className={`py-1.5 px-2 text-right ${c.hitRate >= 50 ? 'text-red-400' : 'text-amber-400'}`}>
                      {c.hitRate.toFixed(1)}%
                    </td>
                    <td className={`py-1.5 px-2 text-right ${c.avgExcessReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {c.avgExcessReturn >= 0 ? '+' : ''}{c.avgExcessReturn.toFixed(3)}%
                    </td>
                    <td className={`py-1.5 px-2 text-right ${c.avgLeaderReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {c.avgLeaderReturn.toFixed(3)}%
                    </td>
                    <td className="py-1.5 px-2 text-right text-slate-400">{c.totalPredictions}</td>
                    <td className="py-1.5 px-2 text-right font-semibold text-accent">
                      {c.compositeScore.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-muted">
        AutoML 搜尋空間：lookback ∈ [5, 10, 15, 20, 30] × forward ∈ [3, 5, 10] = 15 組合。
        評分公式：綜合評分 = 命中率 × 0.6 + 超額收益標準化 × 0.4。
        建議將最佳參數應用於「輪動預測」視圖。
      </p>
    </div>
  );
}
