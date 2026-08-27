'use client';

import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import type { IndustryDailyDto } from '@/lib/api/types';
import { useEChartsOption, DARK_THEME, darkTooltipBase, darkLegendBase } from '@/hooks/useEChartsOption';

interface Props {
  data: IndustryDailyDto[];
}

export function IndustryRisingFalling({ data }: Props) {
  const { option, isEmpty } = useEChartsOption<IndustryDailyDto[]>(data, (raw) => {
    const sorted = [...raw]
      .filter((d) => d.risingCount != null && d.fallingCount != null)
      .sort((a, b) => (b.risingCount ?? 0) - (a.risingCount ?? 0))
      .slice(0, 30);

    const categories = sorted.map((d) => d.industry);
    const rising = sorted.map((d) => d.risingCount ?? 0);
    const falling = sorted.map((d) => d.fallingCount ?? 0);

    return {
      backgroundColor: DARK_THEME.transparent,
      animation: false,
      title: {
        text: '行業漲跌家數圖（按上漲家數排序）',
        left: 'center',
        textStyle: { color: DARK_THEME.titleText, fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        ...darkTooltipBase,
      },
      legend: {
        data: ['上漲家數', '下跌家數'],
        top: 28,
        ...darkLegendBase,
      },
      grid: { left: '3%', right: '4%', bottom: '12%', top: '18%', containLabel: true },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: { rotate: 45, color: DARK_THEME.legendText, fontSize: 10 },
        axisLine: { lineStyle: { color: DARK_THEME.axisLine } },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: DARK_THEME.legendText },
        splitLine: { lineStyle: { color: DARK_THEME.splitLine } },
      },
      series: [
        {
          name: '上漲家數',
          type: 'bar',
          stack: 'total',
          data: rising,
          itemStyle: { color: '#ef4444' },
          label: { show: false },
        },
        {
          name: '下跌家數',
          type: 'bar',
          stack: 'total',
          data: falling,
          itemStyle: { color: '#22c55e' },
          label: { show: false },
        },
      ],
    } as EChartsOption;
  });

  return (
    <div className="rounded-lg border border-border bg-bg-panel p-4 h-[500px]">
      <ReactECharts option={option} style={{ width: '100%', height: '100%' }} />
      {isEmpty && (
        <div className="sr-only" aria-live="polite">暫無數據</div>
      )}
    </div>
  );
}
