'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { IndustryProsperityDto, IndexDailyDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';

interface Props {
  rangeStart: string;
  rangeEnd: string;
}

/**
 * 行業景氣度與大盤指數疊加對比圖。
 *
 * 左軸：全市場平均景氣度（0-100）
 * 右軸：大盤指數（上證綜指）累計漲跌幅（%）
 *
 * 用於觀察行業景氣度與大盤走勢的相關性：
 * - 景氣度領先大盤 → 景氣度上升後大盤跟漲
 * - 景氣度滯後大盤 → 大盤上漲後景氣度才回升
 * - 兩者背離 → 可能出現行業輪動或風格切換
 */
export function ProsperityBenchmarkCompare({ rangeStart, rangeEnd }: Props) {
  // 獲取景氣度歷史數據
  const prosperityKey = `/stock/industry-prosperity/range?start=${rangeStart}&end=${rangeEnd}&topN=20`;
  const {
    data: prosperityData,
    error: prosperityError,
    isLoading: prosperityLoading,
    mutate: mutateProsperity,
    isValidating: prosperityValidating,
  } = useSWR<IndustryProsperityDto[]>(
    prosperityKey,
    () => api.industryProsperityRange(rangeStart, rangeEnd, 20),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );

  // 獲取大盤指數歷史（上證綜指）
  const benchmarkDays = useMemo(() => {
    const start = new Date(rangeStart);
    const end = new Date(rangeEnd);
    const diff = Math.max(1, Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 10);
    return diff;
  }, [rangeStart, rangeEnd]);

  const benchmarkKey = `/stock/index-history?code=sh.000001&days=${benchmarkDays}`;
  const {
    data: benchmarkData,
    error: benchmarkError,
    isLoading: benchmarkLoading,
  } = useSWR<IndexDailyDto[]>(
    benchmarkKey,
    () => api.indexHistory('sh.000001', benchmarkDays),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );

  const option = useMemo(() => {
    if (!prosperityData || prosperityData.length === 0) return null;

    // 1. 按日期分組，計算每日全市場平均景氣度
    const byDate = new Map<string, number[]>();
    for (const item of prosperityData) {
      if (!byDate.has(item.tradeDate)) {
        byDate.set(item.tradeDate, []);
      }
      byDate.get(item.tradeDate)!.push(item.prosperityIndex);
    }

    const dates = Array.from(byDate.keys()).sort();
    const avgProsperity = dates.map((d) => {
      const values = byDate.get(d)!;
      return Number((values.reduce((s, v) => s + v, 0) / values.length).toFixed(2));
    });

    // 2. 計算大盤累計漲跌幅（相對於區間首日）
    const benchmarkMap = new Map<string, number>();
    if (benchmarkData && benchmarkData.length > 0) {
      for (const item of benchmarkData) {
        benchmarkMap.set(item.tradeDate, item.closePrice ?? 0);
      }
    }

    // 對齊日期：取景氣度日期與大盤日期的交集
    const alignedDates: string[] = [];
    const prosperitySeries: number[] = [];
    const benchmarkSeries: number[] = [];

    // 找到大盤的基準價格（第一個匹配的日期）
    let benchmarkBase: number | null = null;
    for (const date of dates) {
      const bp = benchmarkMap.get(date);
      if (bp && bp > 0) {
        benchmarkBase = bp;
        break;
      }
    }

    for (const date of dates) {
      alignedDates.push(date);
      prosperitySeries.push(avgProsperity[dates.indexOf(date)]);

      const bp = benchmarkMap.get(date);
      if (bp && benchmarkBase && benchmarkBase > 0) {
        benchmarkSeries.push(Number(((bp - benchmarkBase) / benchmarkBase * 100).toFixed(3)));
      } else {
        benchmarkSeries.push(null as any);
      }
    }

    return {
      title: {
        text: `行業景氣度 vs 大盤指數（${alignedDates[0]} ~ ${alignedDates[alignedDates.length - 1]}）`,
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
              if (p.seriesName === '全市場平均景氣度') {
                lines.push(`${p.seriesName}: ${p.value.toFixed(1)}`);
              } else {
                lines.push(`${p.seriesName}: ${p.value.toFixed(3)}%`);
              }
            }
          });
          return lines.join('<br/>');
        },
      },
      legend: {
        top: 28,
        textStyle: { color: '#94a3b8', fontSize: 11 },
      },
      grid: { left: '3%', right: '5%', bottom: '15%', top: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: alignedDates,
        axisLabel: { color: '#94a3b8' },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: [
        {
          type: 'value',
          name: '景氣度',
          min: 0,
          max: 100,
          position: 'left',
          axisLabel: { color: '#94a3b8' },
          splitLine: { lineStyle: { color: '#1e293b' } },
        },
        {
          type: 'value',
          name: '大盤漲跌幅(%)',
          position: 'right',
          axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v.toFixed(1)}%` },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, bottom: 5 },
      ],
      series: [
        {
          name: '全市場平均景氣度',
          type: 'line',
          data: prosperitySeries,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          itemStyle: { color: '#38bdf8' },
          lineStyle: { width: 2.5 },
          yAxisIndex: 0,
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(56, 189, 248, 0.15)' },
                { offset: 1, color: 'rgba(56, 189, 248, 0)' },
              ],
            },
          },
        },
        {
          name: '上證綜指累計漲跌幅',
          type: 'line',
          data: benchmarkSeries,
          smooth: true,
          symbol: 'diamond',
          symbolSize: 6,
          itemStyle: { color: '#f59e0b' },
          lineStyle: { width: 2, type: 'dashed' as const },
          yAxisIndex: 1,
          connectNulls: true,
        },
      ],
    };
  }, [prosperityData, benchmarkData]);

  // 計算相關性
  const correlation = useMemo(() => {
    if (!option || !prosperityData || !benchmarkData) return null;

    const byDate = new Map<string, number>();
    for (const item of prosperityData) {
      if (!byDate.has(item.tradeDate)) {
        const values = prosperityData.filter((d) => d.tradeDate === item.tradeDate);
        const avg = values.reduce((s, v) => s + v.prosperityIndex, 0) / values.length;
        byDate.set(item.tradeDate, avg);
      }
    }

    const benchmarkMap = new Map<string, number>();
    for (const item of benchmarkData) {
      benchmarkMap.set(item.tradeDate, item.closePrice ?? 0);
    }

    let benchmarkBase: number | null = null;
    for (const date of Array.from(byDate.keys()).sort()) {
      const bp = benchmarkMap.get(date);
      if (bp && bp > 0) {
        benchmarkBase = bp;
        break;
      }
    }

    const pairs: [number, number][] = [];
    for (const [date, prosperity] of byDate) {
      const bp = benchmarkMap.get(date);
      if (bp && benchmarkBase && benchmarkBase > 0) {
        pairs.push([prosperity, (bp - benchmarkBase) / benchmarkBase * 100]);
      }
    }

    if (pairs.length < 3) return null;

    const n = pairs.length;
    const meanX = pairs.reduce((s, p) => s + p[0], 0) / n;
    const meanY = pairs.reduce((s, p) => s + p[1], 0) / n;
    let num = 0, dx = 0, dy = 0;
    for (const [x, y] of pairs) {
      num += (x - meanX) * (y - meanY);
      dx += (x - meanX) ** 2;
      dy += (y - meanY) ** 2;
    }
    const denom = Math.sqrt(dx * dy);
    return denom === 0 ? 0 : num / denom;
  }, [prosperityData, benchmarkData, option]);

  const isLoading = prosperityLoading || benchmarkLoading;
  const error = prosperityError || benchmarkError;
  const canRender = useDelayedRender(isLoading);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <RefreshButton
          onClick={() => mutateProsperity()}
          isLoading={prosperityValidating}
          className="ml-auto"
        />
      </div>

      {/* 相關性摘要 */}
      {correlation != null && (
        <div className="rounded-lg border border-border bg-bg-panel p-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
            <div>
              <span className="text-muted">景氣度與大盤相關係數：</span>
              <span className={`font-medium ml-1 ${correlation >= 0.5 ? 'text-red-400' : correlation >= 0 ? 'text-amber-400' : 'text-green-400'}`}>
                {correlation.toFixed(3)}
              </span>
            </div>
            <div>
              <span className="text-muted">相關性解讀：</span>
              <span className="text-slate-300 ml-1">
                {correlation >= 0.7 ? '高度正相關（同步走勢）' :
                 correlation >= 0.3 ? '中度正相關（基本同步）' :
                 correlation >= -0.3 ? '弱相關（可能背離）' :
                 correlation >= -0.7 ? '中度負相關（經常背離）' :
                 '高度負相關（走勢相反）'}
              </span>
            </div>
            <div>
              <span className="text-muted">分析建議：</span>
              <span className="text-slate-300 ml-1">
                {correlation >= 0.5 ? '景氣度與大盤同步，可作為大盤趨勢確認' :
                 correlation >= 0 ? '景氣度略有領先/滯後，關注背離信號' :
                 '景氣度與大盤背離，可能出現行業輪動或風格切換'}
              </span>
            </div>
          </div>
        </div>
      )}

      {(isLoading || !canRender) && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutateProsperity()} />}
      {!isLoading && !error && canRender && option && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[500px]">
          <ReactECharts option={option} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}
      {!isLoading && !error && !option && (
        <div className="rounded-lg border border-border bg-bg-panel p-8 text-center text-sm text-muted">
          數據不足，請確認景氣度與大盤指數數據已同步。
        </div>
      )}

      <p className="text-xs text-muted">
        左軸（藍色實線）= 全市場平均景氣度（0-100），右軸（橙色虛線）= 上證綜指相對區間首日的累計漲跌幅（%）。
      </p>
    </div>
  );
}
