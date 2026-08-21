'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { ProsperityForecastBacktestDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { Target, TrendingUp, CheckCircle, AlertCircle } from 'lucide-react';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';

const MONTH_OPTIONS = [3, 6, 12];
const FORECAST_OPTIONS = [3, 5, 10];
const BACKTEST_OPTIONS = [30, 60, 90];

export function ProsperityForecastBacktestPanel() {
  const [months, setMonths] = useState(6);
  const [forecastDays, setForecastDays] = useState(5);
  const [backtestDays, setBacktestDays] = useState(60);

  const key = `/stock/industry-prosperity/forecast/backtest?months=${months}&forecastDays=${forecastDays}&backtestDays=${backtestDays}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<ProsperityForecastBacktestDto>(
    key,
    () => api.prosperityForecastBacktest(months, forecastDays, backtestDays),
    { revalidateOnFocus: false, dedupingInterval: 300_000 }
  );
  const canRender = useDelayedRender(isLoading);

  // MAE 走勢圖
  const maeOption = useMemo(() => {
    if (!data || data.entries.length === 0) return null;

    const maeData = data.entries.map((e) => e.absError);
    const xData = data.entries.map((e) => e.predictDate);

    return {
      title: {
        text: '預測絕對誤差（MAE）走勢',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          const p = params[0];
          const entry = data.entries[p.dataIndex];
          return `${p.name}<br/>預測: ${entry.predictedProsperity.toFixed(1)}<br/>實際: ${entry.actualProsperity.toFixed(1)}<br/>誤差: ${p.value.toFixed(2)}`;
        },
      },
      grid: { left: '5%', right: '5%', bottom: '15%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: xData,
        axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '絕對誤差',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      series: [
        {
          type: 'bar',
          data: maeData.map((v) => ({
            value: v,
            itemStyle: { color: v < 5 ? '#22c55e' : v < 10 ? '#eab308' : '#ef4444' },
          })),
          markLine: {
            data: [{ yAxis: data.mae, name: '平均MAE' }],
            lineStyle: { color: '#38bdf8', type: 'dashed' as const },
            label: { formatter: `平均 ${data.mae.toFixed(2)}`, color: '#38bdf8' },
          },
        },
      ],
    };
  }, [data]);

  // 方向準確率累計圖
  const cumulativeAccuracyOption = useMemo(() => {
    if (!data || data.entries.length === 0) return null;

    let correct = 0;
    const cumulative: number[] = [];
    data.entries.forEach((e, i) => {
      if (e.directionCorrect) correct++;
      cumulative.push((correct / (i + 1)) * 100);
    });

    return {
      title: {
        text: '累計方向準確率',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          const p = params[0];
          return `${p.name}<br/>累計準確率: ${p.value.toFixed(1)}%`;
        },
      },
      grid: { left: '5%', right: '5%', bottom: '15%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: data.entries.map((e) => e.predictDate),
        axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '準確率(%)',
        min: 0,
        max: 100,
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      series: [
        {
          type: 'line',
          data: cumulative,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#38bdf8' },
          lineStyle: { width: 2 },
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
            lineStyle: { color: '#64748b', type: 'dashed' as const },
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
          <Target className="w-4 h-4 text-accent" />
          <span className="text-sm text-muted">景氣度預測回測</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">回溯：</span>
          {MONTH_OPTIONS.map((m) => (
            <button
              key={m}
              onClick={() => setMonths(m)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                months === m ? 'bg-accent/10 text-accent' : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
              }`}
            >
              {m}月
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">預測：</span>
          {FORECAST_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setForecastDays(d)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                forecastDays === d ? 'bg-accent/10 text-accent' : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
              }`}
            >
              {d}日
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">回測：</span>
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

      {/* 指標卡片 */}
      {!isLoading && !error && data && data.totalPredictions > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <AlertCircle className="w-4 h-4 text-amber-400" />
              <p className="text-xs text-muted">MAE（平均絕對誤差）</p>
            </div>
            <p className={`text-lg font-semibold ${data.mae < 5 ? 'text-green-400' : data.mae < 10 ? 'text-amber-400' : 'text-red-400'}`}>
              {data.mae.toFixed(2)}
            </p>
            <p className="text-xs text-muted">{data.mae < 5 ? '優秀' : data.mae < 10 ? '尚可' : '較差'}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-4 h-4 text-blue-400" />
              <p className="text-xs text-muted">方向準確率</p>
            </div>
            <p className={`text-lg font-semibold ${data.directionAccuracy >= 60 ? 'text-red-400' : data.directionAccuracy >= 50 ? 'text-amber-400' : 'text-slate-400'}`}>
              {data.directionAccuracy.toFixed(1)}%
            </p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle className="w-4 h-4 text-green-400" />
              <p className="text-xs text-muted">等級命中率</p>
            </div>
            <p className={`text-lg font-semibold ${data.gradeHitRate >= 50 ? 'text-red-400' : 'text-amber-400'}`}>
              {data.gradeHitRate.toFixed(1)}%
            </p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted mb-1">超額收益</p>
            <p className={`text-lg font-semibold ${data.avgExcessReturn >= 0 ? 'text-red-400' : 'text-green-400'}`}>
              {data.avgExcessReturn >= 0 ? '+' : ''}{data.avgExcessReturn.toFixed(3)}%
            </p>
            <p className="text-xs text-muted">Top vs 市場平均</p>
          </div>
        </div>
      )}

      {/* MAE 走勢圖 */}
      {!isLoading && !error && canRender && maeOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[300px]">
          <ReactECharts option={maeOption} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 累計準確率圖 */}
      {!isLoading && !error && canRender && cumulativeAccuracyOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[300px]">
          <ReactECharts option={cumulativeAccuracyOption} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 回測明細表 */}
      {!isLoading && !error && data && data.entries.length > 0 && (
        <div className="rounded-lg border border-border bg-bg-panel p-4">
          <h4 className="text-sm font-semibold text-slate-100 mb-3">回測明細</h4>
          <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-bg-panel">
                <tr className="border-b border-border text-muted">
                  <th className="text-left py-2 px-2">預測日</th>
                  <th className="text-left py-2 px-2">目標日</th>
                  <th className="text-left py-2 px-2">預測Top</th>
                  <th className="text-left py-2 px-2">實際Top</th>
                  <th className="text-right py-2 px-2">預測值</th>
                  <th className="text-right py-2 px-2">實際值</th>
                  <th className="text-right py-2 px-2">誤差</th>
                  <th className="text-center py-2 px-2">方向</th>
                  <th className="text-center py-2 px-2">等級</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map((e, i) => (
                  <tr key={i} className="border-b border-border/30 hover:bg-bg-hover/30">
                    <td className="py-1.5 px-2 text-slate-300">{e.predictDate}</td>
                    <td className="py-1.5 px-2 text-slate-300">{e.targetDate}</td>
                    <td className="py-1.5 px-2 text-slate-300 truncate max-w-[100px]">{e.topPredicted}</td>
                    <td className="py-1.5 px-2 text-slate-300 truncate max-w-[100px]">{e.topActual}</td>
                    <td className="py-1.5 px-2 text-right text-slate-300">{e.predictedProsperity.toFixed(1)}</td>
                    <td className="py-1.5 px-2 text-right text-slate-300">{e.actualProsperity.toFixed(1)}</td>
                    <td className={`py-1.5 px-2 text-right ${e.absError < 5 ? 'text-green-400' : e.absError < 10 ? 'text-amber-400' : 'text-red-400'}`}>
                      {e.absError.toFixed(2)}
                    </td>
                    <td className="py-1.5 px-2 text-center">
                      {e.directionCorrect ? <span className="text-green-400">✓</span> : <span className="text-red-400">✗</span>}
                    </td>
                    <td className="py-1.5 px-2 text-center">
                      {e.gradeCorrect ? <span className="text-green-400">✓</span> : <span className="text-red-400">✗</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-muted">
        回測邏輯：對每個歷史交易日 T，用 T 之前的數據預測 T+{forecastDays} 日的景氣度，
        比較預測值與實際值。MAE &lt; 5 為優秀，方向準確率 &gt; 55% 為有效預測。
        超額收益 = 預測 Top 行業收益 - 市場平均收益。
      </p>
    </div>
  );
}
