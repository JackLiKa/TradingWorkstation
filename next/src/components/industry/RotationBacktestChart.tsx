'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { RotationBacktestDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshCw, Target, TrendingUp, Award } from 'lucide-react';

const LOOKBACK_OPTIONS = [10, 20, 30];
const FORWARD_OPTIONS = [3, 5, 10];
const BACKTEST_OPTIONS = [60, 90, 180];

export function RotationBacktestChart() {
  const [lookback, setLookback] = useState(20);
  const [forward, setForward] = useState(5);
  const [backtestDays, setBacktestDays] = useState(90);

  const key = `/stock/rotation-prediction/backtest?lookbackDays=${lookback}&forwardDays=${forward}&backtestDays=${backtestDays}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<RotationBacktestDto>(
    key,
    () => api.rotationPredictionBacktest(lookback, forward, backtestDays),
    { revalidateOnFocus: false, dedupingInterval: 120_000 }
  );

  // 超額收益走勢圖
  const excessOption = useMemo(() => {
    if (!data || !data.entries || data.entries.length === 0) return null;

    const dates = data.entries.map((e) => e.predictDate);
    const excessReturns = data.entries.map((e) => e.excessReturn);
    const predictedReturns = data.entries.map((e) => e.predictedReturn);
    const marketReturns = data.entries.map((e) => e.marketAvgReturn);

    return {
      title: {
        text: '輪動預測回測：超額收益走勢',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          const idx = params[0].dataIndex;
          const e = data.entries[idx];
          const lines = [`預測日期: ${e.predictDate}`];
          lines.push(`預測領漲: ${e.topPredicted}`);
          lines.push(`實際領漲: ${e.actualTopIndustry}`);
          lines.push(`--- 收益 ---`);
          lines.push(`預測領漲收益: ${e.predictedReturn.toFixed(3)}%`);
          lines.push(`市場平均收益: ${e.marketAvgReturn.toFixed(3)}%`);
          lines.push(`超額收益: ${e.excessReturn.toFixed(3)}%`);
          lines.push(`命中: ${e.hit ? '✓' : '✗'}`);
          return lines.join('<br/>');
        },
      },
      legend: {
        data: ['預測領漲收益', '市場平均收益', '超額收益'],
        top: 28,
        textStyle: { color: '#94a3b8', fontSize: 10 },
      },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '收益(%)',
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v.toFixed(1)}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, bottom: 5 },
      ],
      series: [
        {
          name: '預測領漲收益',
          type: 'line',
          data: predictedReturns,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#ef4444' },
          lineStyle: { width: 2 },
        },
        {
          name: '市場平均收益',
          type: 'line',
          data: marketReturns,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#64748b' },
          lineStyle: { width: 1.5, type: 'dashed' as const },
        },
        {
          name: '超額收益',
          type: 'bar',
          data: excessReturns.map((v) => ({
            value: v,
            itemStyle: { color: v >= 0 ? '#22c55e' : '#f87171' },
          })),
        },
      ],
    };
  }, [data]);

  // 命中率累計圖
  const hitRateOption = useMemo(() => {
    if (!data || !data.entries || data.entries.length === 0) return null;

    let hits = 0;
    const dates: string[] = [];
    const cumulativeHitRates: number[] = [];
    data.entries.forEach((e, i) => {
      if (e.hit) hits++;
      dates.push(e.predictDate);
      cumulativeHitRates.push(Number(((hits / (i + 1)) * 100).toFixed(1)));
    });

    return {
      title: {
        text: '累計命中率走勢',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          return `${params[0].axisValue}<br/>累計命中率: ${params[0].value.toFixed(1)}%`;
        },
      },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '命中率(%)',
        min: 0,
        max: 100,
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v.toFixed(0)}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      series: [
        {
          type: 'line',
          data: cumulativeHitRates,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#38bdf8' },
          lineStyle: { width: 2.5 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(56, 189, 248, 0.2)' },
                { offset: 1, color: 'rgba(56, 189, 248, 0)' },
              ],
            },
          },
          markLine: {
            data: [{ yAxis: 50, name: '50%基準' }],
            lineStyle: { color: '#f59e0b', type: 'dashed' },
            label: { formatter: '50%基準', color: '#f59e0b' },
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
          <span className="text-sm text-muted">回溯天數：</span>
          {LOOKBACK_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setLookback(d)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                lookback === d ? 'bg-accent/10 text-accent' : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
              }`}
            >
              {d}日
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">前瞻天數：</span>
          {FORWARD_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setForward(d)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                forward === d ? 'bg-accent/10 text-accent' : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
              }`}
            >
              {d}日
            </button>
          ))}
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
          刷新
        </button>
      </div>

      {/* 回測摘要卡片 */}
      {data && data.totalPredictions > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <Target className="w-4 h-4 text-accent" />
              <p className="text-xs text-muted">命中率</p>
            </div>
            <p className={`text-lg font-semibold ${data.hitRate >= 50 ? 'text-red-400' : 'text-amber-400'}`}>
              {data.hitRate.toFixed(1)}%
            </p>
            <p className="text-xs text-muted">{data.hitCount}/{data.totalPredictions} 次命中</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-4 h-4 text-red-400" />
              <p className="text-xs text-muted">預測領漲平均收益</p>
            </div>
            <p className={`text-lg font-semibold ${data.avgLeaderReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
              {data.avgLeaderReturn.toFixed(3)}%
            </p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-4 h-4 text-slate-400" />
              <p className="text-xs text-muted">市場平均收益</p>
            </div>
            <p className={`text-lg font-semibold ${data.avgLaggardReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
              {data.avgLaggardReturn.toFixed(3)}%
            </p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <Award className="w-4 h-4 text-accent" />
              <p className="text-xs text-muted">平均超額收益</p>
            </div>
            <p className={`text-lg font-semibold ${data.avgExcessReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
              {data.avgExcessReturn >= 0 ? '+' : ''}{data.avgExcessReturn.toFixed(3)}%
            </p>
          </div>
        </div>
      )}

      {/* 摘要文字 */}
      {data && data.totalPredictions > 0 && (
        <div className="rounded-md border border-border bg-bg-panel p-3 text-sm text-slate-300">
          {data.summary}
        </div>
      )}

      {isLoading && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}

      {/* 超額收益走勢圖 */}
      {!isLoading && !error && excessOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[450px]">
          <ReactECharts option={excessOption} style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 累計命中率走勢圖 */}
      {!isLoading && !error && hitRateOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[350px]">
          <ReactECharts option={hitRateOption} style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 回測明細表 */}
      {!isLoading && !error && data && data.entries.length > 0 && (
        <div className="rounded-lg border border-border bg-bg-panel p-4">
          <h4 className="text-sm font-semibold text-slate-100 mb-3">回測明細</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-muted">
                  <th className="text-left py-2 px-2">預測日期</th>
                  <th className="text-left py-2 px-2">預測領漲</th>
                  <th className="text-left py-2 px-2">實際領漲</th>
                  <th className="text-right py-2 px-2">預測收益</th>
                  <th className="text-right py-2 px-2">市場平均</th>
                  <th className="text-right py-2 px-2">超額收益</th>
                  <th className="text-center py-2 px-2">命中</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map((e, i) => (
                  <tr key={i} className="border-b border-border/30 hover:bg-bg-hover/30">
                    <td className="py-1.5 px-2 text-slate-400">{e.predictDate}</td>
                    <td className="py-1.5 px-2 text-slate-300 truncate max-w-[120px]" title={e.topPredicted}>
                      {e.topPredicted}
                    </td>
                    <td className="py-1.5 px-2 text-slate-300 truncate max-w-[120px]" title={e.actualTopIndustry}>
                      {e.actualTopIndustry}
                    </td>
                    <td className={`py-1.5 px-2 text-right ${e.predictedReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {e.predictedReturn.toFixed(3)}%
                    </td>
                    <td className={`py-1.5 px-2 text-right ${e.marketAvgReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {e.marketAvgReturn.toFixed(3)}%
                    </td>
                    <td className={`py-1.5 px-2 text-right ${e.excessReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {e.excessReturn >= 0 ? '+' : ''}{e.excessReturn.toFixed(3)}%
                    </td>
                    <td className="py-1.5 px-2 text-center">
                      {e.hit ? (
                        <span className="text-red-400">✓</span>
                      ) : (
                        <span className="text-slate-500">✗</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!isLoading && !error && data && data.totalPredictions === 0 && (
        <div className="rounded-lg border border-border bg-bg-panel p-8 text-center text-sm text-muted">
          {data.summary}
        </div>
      )}

      <p className="text-xs text-muted">
        回測方法：對每個歷史交易日 T，用 T 之前 {lookback} 日數據預測領漲行業，
        再檢查 T 之後 {forward} 日內預測是否命中實際 Top 5。
        命中率 ≥ 50% 表示模型有參考價值，超額收益 &gt; 0 表示預測領漲跑贏市場。
      </p>
    </div>
  );
}
