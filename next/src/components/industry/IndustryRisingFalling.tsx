'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { IndustryDailyDto } from '@/lib/api/types';

interface Props {
  data: IndustryDailyDto[];
}

export function IndustryRisingFalling({ data }: Props) {
  const option = useMemo(() => {
    const sorted = [...data]
      .filter((d) => d.risingCount != null && d.fallingCount != null)
      .sort((a, b) => (b.risingCount ?? 0) - (a.risingCount ?? 0))
      .slice(0, 30);

    const categories = sorted.map((d) => d.industry);
    const rising = sorted.map((d) => d.risingCount ?? 0);
    const falling = sorted.map((d) => d.fallingCount ?? 0);

    return {
      title: {
        text: '行業漲跌家數圖（按上漲家數排序）',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
      },
      legend: {
        data: ['上漲家數', '下跌家數'],
        top: 28,
        textStyle: { color: '#94a3b8' },
      },
      grid: { left: '3%', right: '4%', bottom: '12%', top: '18%', containLabel: true },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: { rotate: 45, color: '#94a3b8', fontSize: 10 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b' } },
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
    };
  }, [data]);

  return (
    <div className="rounded-lg border border-border bg-bg-panel p-4 h-[500px]">
      <ReactECharts option={option} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}
