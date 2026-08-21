'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { RotationPredictionDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { Sparkles, TrendingUp, TrendingDown } from 'lucide-react';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';

const LOOKBACK_OPTIONS = [10, 20, 30, 60];

export function RotationPredictionChart() {
  const [lookback, setLookback] = useState(20);

  const key = `/stock/rotation-prediction?lookbackDays=${lookback}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<RotationPredictionDto>(
    key,
    () => api.rotationPrediction(lookback),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );
  const canRender = useDelayedRender(isLoading);

  const option = useMemo(() => {
    if (!data || !data.predictedLeaders || data.predictedLeaders.length === 0) return null;

    const all = [...data.predictedLeaders, ...data.predictedLaggards];
    const industries = all.map((d) => d.industry.replace(/[A-Z]\d+/, '').trim() || d.industry);
    const scores = all.map((d) => d.score);
    const momentumScores = all.map((d) => d.momentumScore);
    const capitalScores = all.map((d) => d.capitalScore);
    const trendScores = all.map((d) => d.trendScore);

    return {
      title: {
        text: `行業輪動預測（回溯 ${lookback} 日，分析日期 ${data.analysisDate}）`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any[]) => {
          const idx = params[0].dataIndex;
          const d = all[idx];
          const lines = [d.industry];
          lines.push(`綜合評分: ${d.score.toFixed(1)}`);
          lines.push(`--- 分項評分 ---`);
          lines.push(`動量(40%): ${d.momentumScore.toFixed(1)}`);
          lines.push(`資金(35%): ${d.capitalScore.toFixed(1)}`);
          lines.push(`趨勢(25%): ${d.trendScore.toFixed(1)}`);
          lines.push(`--- 分析 ---`);
          lines.push(d.reason);
          return lines.join('<br/>');
        },
      },
      legend: {
        data: ['綜合評分', '動量', '資金', '趨勢'],
        top: 28,
        textStyle: { color: '#94a3b8', fontSize: 10 },
      },
      grid: { left: '3%', right: '4%', bottom: '25%', top: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: industries,
        axisLabel: { rotate: 30, color: '#94a3b8', fontSize: 10, interval: 0 },
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
          name: '綜合評分',
          type: 'bar',
          data: scores.map((v, i) => ({
            value: v,
            itemStyle: {
              color: i < data.predictedLeaders.length ? '#ef4444' : '#22c55e',
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
          data: momentumScores,
          smooth: true,
          itemStyle: { color: '#f59e0b' },
          lineStyle: { width: 1.5 },
          symbol: 'circle',
          symbolSize: 4,
        },
        {
          name: '資金',
          type: 'line',
          data: capitalScores,
          smooth: true,
          itemStyle: { color: '#8b5cf6' },
          lineStyle: { width: 1.5 },
          symbol: 'circle',
          symbolSize: 4,
        },
        {
          name: '趨勢',
          type: 'line',
          data: trendScores,
          smooth: true,
          itemStyle: { color: '#06b6d4' },
          lineStyle: { width: 1.5 },
          symbol: 'circle',
          symbolSize: 4,
        },
      ],
    };
  }, [data, lookback]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">回溯天數：</span>
        {LOOKBACK_OPTIONS.map((d) => (
          <button
            key={d}
            onClick={() => setLookback(d)}
            className={`px-2 py-1 rounded text-xs transition-colors ${
              lookback === d
                ? 'bg-accent/10 text-accent'
                : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
            }`}
          >
            {d} 日
          </button>
        ))}
        <RefreshButton
          onClick={() => mutate()}
          isLoading={isValidating}
          className="ml-auto"
        />
      </div>

      {/* 預測摘要 */}
      {data && (
        <div className="rounded-lg border border-border bg-bg-panel p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" />
            <span className="text-sm font-semibold text-slate-100">輪動預測摘要</span>
            <span className="text-xs text-muted">（信心度: {data.confidence.toFixed(1)}%）</span>
          </div>
          <p className="text-sm text-slate-300">{data.predictionReasoning}</p>
          {/* 信心度進度條 */}
          <div className="w-full h-2 bg-bg-base rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${data.confidence}%`,
                backgroundColor: data.confidence >= 60 ? '#ef4444' : data.confidence >= 30 ? '#f59e0b' : '#64748b',
              }}
            />
          </div>
        </div>
      )}

      {(isLoading || !canRender) && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && canRender && option && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[500px]">
          <ReactECharts option={option} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 預測領漲/滯後行業列表 */}
      {data && (data.predictedLeaders.length > 0 || data.predictedLaggards.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-red-400" />
              <h4 className="text-sm font-semibold text-red-400">預測領漲行業（Top 5）</h4>
            </div>
            <div className="space-y-2">
              {data.predictedLeaders.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-xs border-b border-border/30 pb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-muted font-medium">{i + 1}</span>
                    <span className="text-slate-300 truncate" title={d.industry}>{d.industry}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-red-400 font-medium">{d.score.toFixed(1)}</span>
                    <div className="flex gap-1 text-[10px] text-muted">
                      <span title="動量">M:{d.momentumScore.toFixed(0)}</span>
                      <span title="資金">C:{d.capitalScore.toFixed(0)}</span>
                      <span title="趨勢">T:{d.trendScore.toFixed(0)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown className="w-4 h-4 text-green-400" />
              <h4 className="text-sm font-semibold text-green-400">預測滯後行業（Bottom 5）</h4>
            </div>
            <div className="space-y-2">
              {data.predictedLaggards.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-xs border-b border-border/30 pb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-muted font-medium">{i + 1}</span>
                    <span className="text-slate-300 truncate" title={d.industry}>{d.industry}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-green-400 font-medium">{d.score.toFixed(1)}</span>
                    <div className="flex gap-1 text-[10px] text-muted">
                      <span title="動量">M:{d.momentumScore.toFixed(0)}</span>
                      <span title="資金">C:{d.capitalScore.toFixed(0)}</span>
                      <span title="趨勢">T:{d.trendScore.toFixed(0)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <p className="text-xs text-muted">
        預測模型：動量延續(40%) + 資金流向(35%) + 景氣度趨勢(25%)。紅色 = 預測領漲，綠色 = 預測滯後。
        信心度基於 Top 1 與中位數的差距，越高表示預測越確定。
      </p>
    </div>
  );
}
