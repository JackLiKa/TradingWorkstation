'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { IndustryDailyDto } from '@/lib/api/types';

interface Props {
  data: IndustryDailyDto[];
}

export function IndustryTreemap({ data }: Props) {
  const option = useMemo(() => {
    const top = data
      .filter((d) => d.avgPctChg != null && d.totalAmount != null)
      .slice(0, 60);

    const treeData = top.map((d) => ({
      name: d.industry,
      value: [d.avgPctChg ?? 0, d.totalAmount ?? 0],
      itemStyle: {
        color: getColor(d.avgPctChg ?? 0),
      },
      label: {
        show: true,
        formatter: `{b}\n{c[0]}%`,
        fontSize: 10,
      },
    }));

    return {
      title: {
        text: '行業熱力圖（按成交額與平均漲跌幅）',
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        formatter: (params: any) => {
          const v = params.value;
          return `${params.name}<br/>平均漲跌幅: ${v[0].toFixed(3)}%<br/>成交金額: ${v[1].toLocaleString()}`;
        },
      },
      series: [
        {
          type: 'treemap',
          width: '100%',
          height: '100%',
          data: treeData,
          leafDepth: 1,
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          itemStyle: {
            borderColor: '#0f172a',
            borderWidth: 1,
            gapWidth: 1,
          },
          label: {
            show: true,
            formatter: '{b}\n{c[0]}%',
            color: '#fff',
          },
          upperLabel: { show: false },
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

function getColor(pct: number) {
  if (pct > 5) return '#ef4444';
  if (pct > 2) return '#f87171';
  if (pct > 0) return '#fca5a5';
  if (pct > -2) return '#86efac';
  if (pct > -5) return '#4ade80';
  return '#22c55e';
}
