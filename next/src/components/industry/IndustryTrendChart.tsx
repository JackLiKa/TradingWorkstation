'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { IndustryDailyDto, IndexDailyDto } from '@/lib/api/types';
import type { IndustryNewsItem } from '@/lib/api/agent';

interface Props {
  data: IndustryDailyDto[];
  news?: IndustryNewsItem[];
  benchmark?: IndexDailyDto[];
  benchmarkLabel?: string;
}

export function IndustryTrendChart({ data, news = [], benchmark = [], benchmarkLabel = '上證綜指' }: Props) {
  const option = useMemo(() => {
    const sorted = [...data].sort(
      (a, b) => new Date(a.tradeDate).getTime() - new Date(b.tradeDate).getTime()
    );
    const dates = sorted.map((d) => d.tradeDate);
    const pctValues = sorted.map((d) => (d.avgPctChg == null ? 0 : d.avgPctChg));
    const amountValues = sorted.map((d) => (d.totalAmount == null ? 0 : d.totalAmount));

    // 大盤指數對齊到行業日期（缺失日期用 null）
    const benchmarkMap = new Map(benchmark.map((b) => [b.tradeDate, b.pctChange]));
    const benchmarkValues = dates.map((d) => {
      const v = benchmarkMap.get(d);
      return v == null ? null : v;
    });

    // 構建新聞 markPoints：只標記在 dates 範圍內的新聞
    const dateSet = new Set(dates);
    const newsMarks = news
      .filter((n) => n.date && dateSet.has(n.date))
      .slice(0, 10)
      .map((n) => {
        const idx = dates.indexOf(n.date);
        const pct = pctValues[idx] ?? 0;
        return {
          name: n.title.slice(0, 20),
          coord: [n.date, pct],
          value: '新聞',
          itemStyle: { color: '#f59e0b' },
          label: {
            show: true,
            formatter: '📰',
            fontSize: 14,
            color: '#f59e0b',
          },
        };
      });

    const seriesList: any[] = [
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
        markPoint: {
          data: newsMarks,
          symbol: 'pin',
          symbolSize: 40,
        },
      },
      {
        name: '成交金額',
        type: 'bar',
        data: amountValues,
        yAxisIndex: 1,
        itemStyle: { color: '#f59e0b' },
      },
    ];

    if (benchmark.length > 0) {
      seriesList.push({
        name: benchmarkLabel,
        type: 'line',
        data: benchmarkValues,
        smooth: true,
        yAxisIndex: 0,
        itemStyle: { color: '#ef4444' },
        lineStyle: { type: 'dashed', width: 1.5 },
        symbol: 'circle',
        symbolSize: 5,
      });
    }

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
          const bench = params.find((p) => p.seriesName === benchmarkLabel);
          const lines = [date];
          if (pct) lines.push(`平均漲跌幅: ${Number(pct.value).toFixed(3)}%`);
          if (bench && bench.value != null) lines.push(`${benchmarkLabel}: ${Number(bench.value).toFixed(3)}%`);
          if (amount) lines.push(`成交金額: ${Number(amount.value).toLocaleString()}`);
          // 當日新聞
          const dayNews = news.filter((n) => n.date === date);
          if (dayNews.length > 0) {
            lines.push('');
            lines.push('--- 相關新聞 ---');
            dayNews.slice(0, 3).forEach((n) => {
              lines.push(`• ${n.title}`);
            });
            if (dayNews.length > 3) lines.push(`...共 ${dayNews.length} 條`);
          }
          return lines.join('<br/>');
        },
      },
      legend: {
        data: benchmark.length > 0 ? ['平均漲跌幅', '成交金額', benchmarkLabel] : ['平均漲跌幅', '成交金額'],
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
      series: seriesList,
    };
  }, [data, news, benchmark, benchmarkLabel]);

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
