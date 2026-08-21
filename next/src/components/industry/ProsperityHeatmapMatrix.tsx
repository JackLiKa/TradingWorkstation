'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { IndustryProsperityDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';

interface Props {
  rangeStart: string;
  rangeEnd: string;
}

/**
 * 行業景氣度熱力圖矩陣（多日 × 多行業）。
 *
 * 橫軸：日期（按時間升序）
 * 縱軸：行業（按末日景氣度倒序）
 * 顏色：景氣度 0-100（綠=低 → 黃=中 → 紅=高）
 */
export function ProsperityHeatmapMatrix({ rangeStart, rangeEnd }: Props) {
  const key = `/stock/industry-prosperity/range?start=${rangeStart}&end=${rangeEnd}&topN=20`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<IndustryProsperityDto[]>(
    key,
    () => api.industryProsperityRange(rangeStart, rangeEnd, 20),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );
  const canRender = useDelayedRender(isLoading);

  const option = useMemo(() => {
    if (!data || data.length === 0) return null;

    // 按日期分組
    const byDate = new Map<string, Map<string, number>>();
    for (const item of data) {
      if (!byDate.has(item.tradeDate)) {
        byDate.set(item.tradeDate, new Map());
      }
      byDate.get(item.tradeDate)!.set(item.industry, item.prosperityIndex);
    }

    const dates = Array.from(byDate.keys()).sort();
    if (dates.length === 0) return null;

    // 取最後一個日期的行業排序（按景氣度倒序）
    const lastDate = dates[dates.length - 1];
    const lastDateData = byDate.get(lastDate)!;
    const industries = Array.from(lastDateData.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([ind]) => ind);

    // 構建熱力圖數據 [xIndex, yIndex, value]
    const heatmapData: [number, number, number][] = [];
    for (let y = 0; y < industries.length; y++) {
      for (let x = 0; x < dates.length; x++) {
        const value = byDate.get(dates[x])?.get(industries[y]);
        if (value != null) {
          heatmapData.push([x, y, Number(value.toFixed(1))]);
        }
      }
    }

    // 簡化行業名稱
    const shortIndustries = industries.map((name) => {
      const match = name.match(/[A-Z]\d+(.*)/);
      return match ? match[1] : name;
    });

    return {
      title: {
        text: `行業景氣度熱力圖矩陣（${dates[0]} ~ ${lastDate}）`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const [x, y, value] = params.value;
          return `${industries[y]}<br/>${dates[x]}<br/>景氣度: <b>${value.toFixed(1)}</b>`;
        },
      },
      grid: {
        left: '18%',
        right: '5%',
        bottom: '15%',
        top: '15%',
      },
      xAxis: {
        type: 'category',
        data: dates,
        splitArea: { show: true },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          rotate: 45,
        },
      },
      yAxis: {
        type: 'category',
        data: shortIndustries,
        splitArea: { show: true },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
        },
      },
      visualMap: {
        min: 0,
        max: 100,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '2%',
        textStyle: { color: '#94a3b8' },
        inRange: {
          color: ['#22c55e', '#84cc16', '#fbbf24', '#f59e0b', '#ef4444'],
        },
      },
      series: [
        {
          name: '景氣度',
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: dates.length <= 15 && industries.length <= 15,
            color: '#fff',
            fontSize: 9,
            formatter: (p: any) => p.value[2].toFixed(0),
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    };
  }, [data]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <RefreshButton
          onClick={() => mutate()}
          isLoading={isValidating}
          className="ml-auto"
        />
      </div>

      {(isLoading || !canRender) && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && canRender && option && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[600px]">
          <ReactECharts option={option} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}
      {!isLoading && !error && !option && (
        <div className="rounded-lg border border-border bg-bg-panel p-8 text-center text-sm text-muted">
          數據不足，請確認景氣度數據已同步。
        </div>
      )}

      <p className="text-xs text-muted">
        熱力圖矩陣展示各行業在不同日期的景氣度變化。顏色從綠（低景氣度）到紅（高景氣度），
        可直觀觀察行業景氣度的時間變化趨勢和行業間差異。
      </p>
    </div>
  );
}
