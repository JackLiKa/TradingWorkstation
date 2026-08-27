'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { ProsperityForecastDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { LineChart, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';
import { AnalysisTutorial } from '@/components/industry/AnalysisTutorial';

const MONTH_OPTIONS = [3, 6, 12];
const FORECAST_OPTIONS = [3, 5, 10];

const TREND_CONFIG = {
  '上升': { icon: TrendingUp, color: 'text-red-400', bg: 'bg-red-500/10' },
  '下降': { icon: TrendingDown, color: 'text-green-400', bg: 'bg-green-500/10' },
  '平穩': { icon: Minus, color: 'text-slate-400', bg: 'bg-slate-500/10' },
};

export function ProsperityForecastPanel() {
  const [months, setMonths] = useState(6);
  const [forecastDays, setForecastDays] = useState(5);
  const [selectedIndustry, setSelectedIndustry] = useState<string>('');

  const key = `/stock/industry-prosperity/forecast?months=${months}&forecastDays=${forecastDays}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<ProsperityForecastDto>(
    key,
    () => api.prosperityForecast(months, forecastDays),
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

  // 共識趨勢排行
  const consensusRanking = useMemo(() => {
    if (!data || !data.industries) return { up: [], down: [], flat: [] };
    const all = Object.values(data.industries);
    const up = all.filter((f) => f.consensusTrend === '上升')
      .sort((a, b) => {
        const aDelta = a.ensembleForecast[a.ensembleForecast.length - 1] - a.currentProsperity;
        const bDelta = b.ensembleForecast[b.ensembleForecast.length - 1] - b.currentProsperity;
        return bDelta - aDelta;
      });
    const down = all.filter((f) => f.consensusTrend === '下降')
      .sort((a, b) => {
        const aDelta = a.ensembleForecast[a.ensembleForecast.length - 1] - a.currentProsperity;
        const bDelta = b.ensembleForecast[b.ensembleForecast.length - 1] - b.currentProsperity;
        return aDelta - bDelta;
      });
    const flat = all.filter((f) => f.consensusTrend === '平穩');
    return { up: up.slice(0, 5), down: down.slice(0, 5), flat };
  }, [data]);

  // 多模型預測走勢圖
  const forecastOption = useMemo(() => {
    if (!data || !selectedIndustry || !data.industries[selectedIndustry]) return null;
    const f = data.industries[selectedIndustry];

    // 構建 x 軸：當前 + 預測日期
    const xData = ['當前', ...f.forecastDates];

    // 當前值 + 預測值
    const arimaData = [f.currentProsperity, ...f.arimaForecast];
    const hwData = [f.currentProsperity, ...f.holtWintersForecast];
    const linearData = [f.currentProsperity, ...f.linearForecast];
    const ensembleData = [f.currentProsperity, ...f.ensembleForecast];

    return {
      title: {
        text: `${selectedIndustry} — 多模型景氣度預測`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['ARIMA', 'Holt-Winters', '線性回歸', '整合預測'],
        top: 28,
        textStyle: { color: '#94a3b8', fontSize: 10 },
      },
      grid: { left: '5%', right: '5%', bottom: '15%', top: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: xData,
        axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '景氣度',
        min: 0,
        max: 100,
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      series: [
        {
          name: 'ARIMA',
          type: 'line',
          data: arimaData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#3b82f6' },
          lineStyle: { width: 1.5, type: 'dashed' as const },
        },
        {
          name: 'Holt-Winters',
          type: 'line',
          data: hwData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#22c55e' },
          lineStyle: { width: 1.5, type: 'dashed' as const },
        },
        {
          name: '線性回歸',
          type: 'line',
          data: linearData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#eab308' },
          lineStyle: { width: 1.5, type: 'dashed' as const },
        },
        {
          name: '整合預測',
          type: 'line',
          data: ensembleData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 7,
          itemStyle: { color: '#ef4444' },
          lineStyle: { width: 2.5 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(239, 68, 68, 0.15)' },
                { offset: 1, color: 'rgba(239, 68, 68, 0)' },
              ],
            },
          },
        },
      ],
    };
  }, [data, selectedIndustry]);

  return (
    <div className="space-y-3">
      <AnalysisTutorial tutorialKey="prosperityForecast" />
      {/* 參數選擇器 */}
      <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-bg-panel p-3">
        <div className="flex items-center gap-2">
          <LineChart className="w-4 h-4 text-accent" />
          <span className="text-sm text-muted">多模型預測</span>
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

      {/* 共識趨勢排行 */}
      {!isLoading && !error && data && (consensusRanking.up.length > 0 || consensusRanking.down.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-red-400" />
              <h4 className="text-sm font-semibold text-red-400">共識上升 Top 5</h4>
            </div>
            <ul className="space-y-1">
              {consensusRanking.up.map((f, i) => (
                <li key={i} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{f.industry}</span>
                  <span className="text-red-400 flex-shrink-0 ml-2">
                    {f.currentProsperity.toFixed(1)} → {f.ensembleForecast[f.ensembleForecast.length - 1].toFixed(1)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-3">
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown className="w-4 h-4 text-green-400" />
              <h4 className="text-sm font-semibold text-green-400">共識下降 Top 5</h4>
            </div>
            <ul className="space-y-1">
              {consensusRanking.down.map((f, i) => (
                <li key={i} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{f.industry}</span>
                  <span className="text-green-400 flex-shrink-0 ml-2">
                    {f.currentProsperity.toFixed(1)} → {f.ensembleForecast[f.ensembleForecast.length - 1].toFixed(1)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
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

      {/* 三模型趨勢卡片 */}
      {!isLoading && !error && data && selectedIndustry && data.industries[selectedIndustry] && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {(['arimaTrend', 'holtWintersTrend', 'linearTrend', 'consensusTrend'] as const).map((key) => {
            const trend = data.industries[selectedIndustry][key];
            const config = TREND_CONFIG[trend as keyof typeof TREND_CONFIG] || TREND_CONFIG['平穩'];
            const Icon = config.icon;
            const label = key === 'arimaTrend' ? 'ARIMA' : key === 'holtWintersTrend' ? 'Holt-Winters' : key === 'linearTrend' ? '線性回歸' : '共識';
            return (
              <div key={key} className={`rounded-lg border border-border p-3 ${key === 'consensusTrend' ? 'bg-accent/5 border-accent/30' : 'bg-bg-panel'}`}>
                <p className="text-xs text-muted mb-1">{label}</p>
                <div className={`flex items-center gap-1 ${config.color}`}>
                  <Icon className="w-4 h-4" />
                  <span className="text-sm font-semibold">{trend}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 多模型預測走勢圖 */}
      {!isLoading && !error && canRender && forecastOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[400px]">
          <ReactECharts option={forecastOption} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      <p className="text-xs text-muted">
        三個輕量級 CPU 模型（純 Java 實作，秒級運算）：
        ARIMA（AR(2)+一階差分，捕捉自相關）、Holt-Winters（三重指數平滑，捕捉趨勢+季節性）、線性回歸（OLS 趨勢）。
        整合預測 = ARIMA × 0.35 + Holt-Winters × 0.35 + 線性回歸 × 0.30。
        共識趨勢 = 三模型多數決（≥2 個一致）。
      </p>
    </div>
  );
}
