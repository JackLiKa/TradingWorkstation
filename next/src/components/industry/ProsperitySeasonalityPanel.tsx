'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { ProsperitySeasonalityDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { Calendar, TrendingUp, Flame } from 'lucide-react';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';
import { AnalysisTutorial } from '@/components/industry/AnalysisTutorial';

const MONTH_OPTIONS = [6, 12, 24, 36];
const MONTH_NAMES = ['', '1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
const WEEKDAY_NAMES = ['', '週一', '週二', '週三', '週四', '週五', '週六', '週日'];

export function ProsperitySeasonalityPanel() {
  const [months, setMonths] = useState(12);
  const [selectedIndustry, setSelectedIndustry] = useState<string>('');

  const key = `/stock/industry-prosperity/seasonality?months=${months}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<ProsperitySeasonalityDto>(
    key,
    () => api.prosperitySeasonality(months),
    { revalidateOnFocus: false, dedupingInterval: 300_000 }
  );
  const canRender = useDelayedRender(isLoading);

  const industries = useMemo(() => {
    if (!data || !data.industries) return [];
    return Object.keys(data.industries).sort();
  }, [data]);

  // 自動選擇第一個行業
  useMemo(() => {
    if (industries.length > 0 && !selectedIndustry) {
      setSelectedIndustry(industries[0]);
    }
  }, [industries, selectedIndustry]);

  // 季節性強度排行
  const seasonalityRanking = useMemo(() => {
    if (!data || !data.industries) return [];
    return Object.values(data.industries)
      .sort((a, b) => b.seasonalityStrength - a.seasonalityStrength)
      .slice(0, 10);
  }, [data]);

  // 月度模式圖（選中行業）
  const monthlyOption = useMemo(() => {
    if (!data || !selectedIndustry || !data.industries[selectedIndustry]) return null;
    const pattern = data.industries[selectedIndustry];

    const monthData: number[] = [];
    for (let m = 1; m <= 12; m++) {
      monthData.push(pattern.monthlyAvg[m] ?? null as any);
    }

    return {
      title: {
        text: `${selectedIndustry} — 月度景氣度模式`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          const p = params[0];
          if (p.value == null) return `${p.name}<br/>無數據`;
          return `${p.name}<br/>平均景氣度: ${p.value.toFixed(1)}`;
        },
      },
      grid: { left: '5%', right: '5%', bottom: '10%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: MONTH_NAMES.slice(1),
        axisLabel: { color: '#94a3b8' },
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
          type: 'bar',
          data: monthData.map((v) => {
            if (v == null) return { value: null };
            return {
              value: v,
              itemStyle: {
                color: v >= 65 ? '#ef4444' : v >= 50 ? '#eab308' : v >= 35 ? '#3b82f6' : '#1e40af',
              },
            };
          }),
          label: {
            show: true,
            position: 'top',
            color: '#94a3b8',
            fontSize: 10,
            formatter: (p: any) => (p.value != null ? p.value.toFixed(1) : ''),
          },
          markLine: {
            data: [{ yAxis: pattern.overallAvg, name: '整體平均' }],
            lineStyle: { color: '#38bdf8', type: 'dashed' },
            label: { formatter: `平均 ${pattern.overallAvg.toFixed(1)}`, color: '#38bdf8' },
          },
        },
      ],
    };
  }, [data, selectedIndustry]);

  // 星期模式圖（選中行業）
  const weekdayOption = useMemo(() => {
    if (!data || !selectedIndustry || !data.industries[selectedIndustry]) return null;
    const pattern = data.industries[selectedIndustry];

    const weekdayData: number[] = [];
    for (let w = 1; w <= 5; w++) {
      weekdayData.push(pattern.weekdayAvg[w] ?? null as any);
    }

    return {
      title: {
        text: `${selectedIndustry} — 星期景氣度模式`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          const p = params[0];
          if (p.value == null) return `${p.name}<br/>無數據`;
          return `${p.name}<br/>平均景氣度: ${p.value.toFixed(1)}`;
        },
      },
      grid: { left: '5%', right: '5%', bottom: '10%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: WEEKDAY_NAMES.slice(1, 6),
        axisLabel: { color: '#94a3b8' },
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
          type: 'line',
          data: weekdayData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 8,
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
        },
      ],
    };
  }, [data, selectedIndustry]);

  // 季節性強度排行圖
  const rankingOption = useMemo(() => {
    if (seasonalityRanking.length === 0) return null;

    return {
      title: {
        text: '季節性強度排行 Top 10',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          const p = params[0];
          const pattern = seasonalityRanking[p.dataIndex];
          return `${p.name}<br/>季節性強度: ${(p.value * 100).toFixed(1)}%<br/>最佳月份: ${MONTH_NAMES[pattern.bestMonth]} (${pattern.bestMonthAvg.toFixed(1)})<br/>最差月份: ${MONTH_NAMES[pattern.worstMonth]} (${pattern.worstMonthAvg.toFixed(1)})`;
        },
      },
      grid: { left: '3%', right: '5%', bottom: '5%', top: '15%', containLabel: true },
      xAxis: {
        type: 'value',
        name: '季節性強度',
        max: 1,
        axisLabel: { color: '#94a3b8', formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      yAxis: {
        type: 'category',
        data: seasonalityRanking.map((p) => p.industry).reverse(),
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      series: [
        {
          type: 'bar',
          data: seasonalityRanking.map((p) => p.seasonalityStrength).reverse(),
          itemStyle: {
            color: (p: any) => {
              const v = p.value;
              if (v >= 0.5) return '#ef4444';
              if (v >= 0.3) return '#eab308';
              if (v >= 0.15) return '#3b82f6';
              return '#1e40af';
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
  }, [seasonalityRanking]);

  return (
    <div className="space-y-3">
      <AnalysisTutorial tutorialKey="prosperitySeasonality" />
      {/* 參數選擇器 */}
      <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-bg-panel p-3">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-accent" />
          <span className="text-sm text-muted">分析區間：</span>
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

      {/* 季節性強度排行 */}
      {!isLoading && !error && canRender && rankingOption && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[400px]">
          <ReactECharts option={rankingOption} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 行業選擇器 */}
      {!isLoading && !error && canRender && industries.length > 0 && (
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

      {/* 月度模式 + 星期模式 */}
      {!isLoading && !error && canRender && monthlyOption && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-4 h-[350px]">
            <ReactECharts option={monthlyOption} notMerge style={{ width: '100%', height: '100%' }} />
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-4 h-[350px]">
            <ReactECharts option={weekdayOption} notMerge style={{ width: '100%', height: '100%' }} />
          </div>
        </div>
      )}

      {/* 選中行業的季節性摘要卡片 */}
      {!isLoading && !error && canRender && data && selectedIndustry && data.industries[selectedIndustry] && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <Flame className="w-4 h-4 text-red-400" />
              <p className="text-xs text-muted">最佳月份</p>
            </div>
            <p className="text-lg font-semibold text-red-400">{MONTH_NAMES[data.industries[selectedIndustry].bestMonth]}</p>
            <p className="text-xs text-muted">景氣度 {data.industries[selectedIndustry].bestMonthAvg.toFixed(1)}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-4 h-4 text-blue-400" />
              <p className="text-xs text-muted">最差月份</p>
            </div>
            <p className="text-lg font-semibold text-blue-400">{MONTH_NAMES[data.industries[selectedIndustry].worstMonth]}</p>
            <p className="text-xs text-muted">景氣度 {data.industries[selectedIndustry].worstMonthAvg.toFixed(1)}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted mb-1">季節性強度</p>
            <p className="text-lg font-semibold text-accent">
              {(data.industries[selectedIndustry].seasonalityStrength * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-muted">
              {data.industries[selectedIndustry].seasonalityStrength >= 0.3 ? '強季節性' :
               data.industries[selectedIndustry].seasonalityStrength >= 0.15 ? '中等季節性' : '弱季節性'}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted mb-1">整體平均景氣度</p>
            <p className="text-lg font-semibold text-slate-100">{data.industries[selectedIndustry].overallAvg.toFixed(1)}</p>
          </div>
        </div>
      )}

      <p className="text-xs text-muted">
        季節性強度 = 月度方差 / 總方差（0-100%）。≥30% 表示強季節性模式，
        該行業景氣度有明顯的月度規律，可在最佳月份前佈局、最差月份前離場。
      </p>
    </div>
  );
}
