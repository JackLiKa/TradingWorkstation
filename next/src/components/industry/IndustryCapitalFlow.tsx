'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { IndustryDailyDto } from '@/lib/api/types';

interface Props {
  data: IndustryDailyDto[];
}

export function IndustryCapitalFlow({ data }: Props) {
  const option = useMemo(() => {
    const sorted = [...data]
      .filter((d) => d.totalAmount != null)
      .sort((a, b) => (b.totalAmount ?? 0) - (a.totalAmount ?? 0))
      .slice(0, 25);

    const categories = sorted.map((d) => d.industry);
    // 轉為億元（1 億 = 1e8）
    const values = sorted.map((d) => Number(((d.totalAmount ?? 0) / 1e8).toFixed(2)));

    return {
      title: {
        text: '資金流向排行（成交金額 Top 25，單位：億元）',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const p = params[0];
          return `${p.name}<br/>成交金額: ${Number(p.value).toFixed(2)} 億元`;
        },
      },
      grid: { left: '3%', right: '4%', bottom: '12%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: { rotate: 45, color: '#94a3b8', fontSize: 10 },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: {
        type: 'value',
        name: '億元',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      series: [
        {
          type: 'bar',
          data: values,
          itemStyle: {
            color: '#3b82f6',
            borderRadius: [4, 4, 0, 0],
          },
          label: {
            show: true,
            position: 'top',
            color: '#94a3b8',
            fontSize: 10,
            formatter: (p: any) => `${p.value.toFixed(1)}億`,
          },
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
