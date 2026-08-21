'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { IndustryDailyDto } from '@/lib/api/types';

interface Props {
  data: IndustryDailyDto[];
}

export function IndustryTrendChart({ data }: Props) {
  const option = useMemo(() => {
    const sorted = [...data].sort(
      (a, b) => new Date(a.tradeDate).getTime() - new Date(b.tradeDate).getTime()
    );
    const dates = sorted.map((d) => d.tradeDate);
    const pctValues = sorted.map((d) => (d.avgPctChg == null ? 0 : d.avgPctChg));
    const amountValues = sorted.map((d) => (d.totalAmount == null ? 0 : d.totalAmount));

    return {
      title: {
        text: '單一行業歷史走勢',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any[]) => {
          const date = params[0].axisValue;
          const pct = params.find((p) => p.seriesName === '平均漲跌幅');
          const amount = params.find((p) => p.seriesName === '成交金額');
          const lines = [date];
          if (pct) lines.push(`平均漲跌幅: ${pct.value.toFixed(3)}%`);
          if (amount) lines.push(`成交金額: ${Number(amount.value).toLocaleString()}`);
          return lines.join('<br/>');
        },
      },
      legend: {
        data: ['平均漲跌幅', '成交金額'],
        top: 28,
        textStyle: { color: '#94a3b8' },
      },
      grid: { left: '3%', right: '4%', bottom: '12%', top: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: '#94a3b8' },
        axisLine: { lineStyle: { color: '#334155' } },
      },
      yAxis: [
        {
          type: 'value',
          name: '漲跌幅(%)',
          axisLabel: { color: '#94a3b8' },
          splitLine: { lineStyle: { color: '#1e293b' } },
        },
        {
          type: 'value',
          name: '成交金額',
          axisLabel: { color: '#94a3b8', formatter: (v: number) => formatAmount(v) },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, bottom: 10 },
      ],
      series: [
        {
          name: '平均漲跌幅',
          type: 'line',
          data: pctValues,
          smooth: true,
          yAxisIndex: 0,
          itemStyle: { color: '#3b82f6' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(59,130,246,0.4)' },
                { offset: 1, color: 'rgba(59,130,246,0.05)' },
              ],
            },
          },
          markLine: {
            data: [{ yAxis: 0, lineStyle: { color: '#64748b' } }],
          },
        },
        {
          name: '成交金額',
          type: 'bar',
          data: amountValues,
          yAxisIndex: 1,
          itemStyle: { color: '#f59e0b' },
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

function formatAmount(value: number) {
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toString();
}
