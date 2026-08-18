/**
 * @file BacktestCurveChart 組件 — 回測淨值曲線圖，
 * 使用 ECharts 展示策略淨值、基準淨值和超額收益三條曲線。
 */
'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EquityPoint } from '@/lib/api/types';

/** BacktestCurveChart 組件屬性 */
interface Props {
  /** 策略淨值曲線數據 */
  strategy: EquityPoint[];
  /** 基準淨值曲線數據（上證綜指） */
  benchmark: EquityPoint[];
  /** 超額收益曲線數據 */
  excess: EquityPoint[];
}

/**
 * BacktestCurveChart 組件 — 回測淨值曲線圖。
 * 雙 Y 軸：左軸顯示策略/基準淨值，右軸顯示超額收益；支持 dataZoom 縮放。
 * @param strategy 策略淨值曲線
 * @param benchmark 基準淨值曲線
 * @param excess 超額收益曲線
 */
export function BacktestCurveChart({ strategy, benchmark, excess }: Props) {
  const option = useMemo(() => {
    const dates = strategy.map((p) => p.date);
    return {
      backgroundColor: 'transparent',
      animation: false,
      legend: { top: 0, textStyle: { color: '#94a3b8' }, data: ['策略净值', '基准净值(上证综指)', '超额收益'] },
      tooltip: { trigger: 'axis', backgroundColor: '#0f172a', borderColor: '#1e293b', textStyle: { color: '#e2e8f0' } },
      grid: { left: '8%', right: '4%', top: 40, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b' } },
      yAxis: [
        { type: 'value', scale: true, axisLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#16213a' } } },
        { type: 'value', scale: true, axisLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b' }, splitLine: { show: false } },
      ],
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 16, bottom: 8, borderColor: '#1e293b', fillerColor: 'rgba(56,189,248,0.1)' },
      ],
      series: [
        { name: '策略净值', type: 'line', data: strategy.map((p) => p.value), symbol: 'none', lineStyle: { width: 2, color: '#38bdf8' } },
        { name: '基准净值(上证综指)', type: 'line', data: benchmark.map((p) => p.value), symbol: 'none', lineStyle: { width: 2, color: '#f59e0b' } },
        { name: '超额收益', type: 'line', yAxisIndex: 1, data: excess.map((p) => p.value), symbol: 'none', lineStyle: { width: 1.5, color: '#a855f7' }, areaStyle: { color: 'rgba(168,85,247,0.08)' } },
      ],
    };
  }, [strategy, benchmark, excess]);

  return (
    <div className="rounded-lg border border-border bg-bg-panel p-4">
      <h3 className="text-base font-semibold text-slate-100 mb-3">回测净值曲线</h3>
      <ReactECharts option={option} style={{ height: 400 }} notMerge lazyUpdate theme="dark" />
    </div>
  );
}
