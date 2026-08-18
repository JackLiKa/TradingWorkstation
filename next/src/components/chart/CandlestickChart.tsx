/**
 * @file CandlestickChart 組件 — 日線 K 線圖，使用 ECharts 展示
 * K線 + 成交量 + MACD + KDJ 四面板佈局，支持加載更早歷史數據和縮放操作。
 */
'use client';

import { useMemo, useRef, useState, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import type { CandlestickDto } from '@/lib/api/types';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Loader2, ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react';

/** CandlestickChart 組件屬性 */
interface Props {
  /** 初始 K線數據（含記錄和技術指標） */
  initial: CandlestickDto;
  /** 復權類型 */
  adjustflag: number;
  /** 開始日期（可選） */
  startDate?: string | null;
  /** 結束日期（可選） */
  endDate?: string | null;
}

/**
 * CandlestickChart 組件 — 日線 K 線圖。
 * 四面板佈局：K線主圖 + 成交量 + MACD + KDJ，支持加載更早數據和 dataZoom 縮放。
 * @param initial 初始 K線數據
 * @param adjustflag 復權類型
 * @param startDate 開始日期
 * @param endDate 結束日期
 */
export function CandlestickChart({ initial, adjustflag, startDate, endDate }: Props) {
  const [data, setData] = useState<CandlestickDto>(initial);
  const [loading, setLoading] = useState(false);
  const chartRef = useRef<ReactECharts>(null);

  const loadOlder = useCallback(async () => {
    if (!data.hasMore || loading || data.records.length === 0) return;
    setLoading(true);
    try {
      const beforeDate = data.records[0].tradeDate;
      const params = new URLSearchParams({
        code: data.code,
        adjustflag: String(adjustflag),
        beforeDate,
      });
      if (startDate) params.set('startDate', startDate);
      if (endDate) params.set('endDate', endDate);
      const older = await api.olderCandlestick(params);
      if (older.records.length > 0) {
        setData((prev) => ({
          ...older,
          records: [...older.records, ...prev.records],
          indicators: mergeIndicators(older.indicators, prev.indicators, older.records.length),
        }));
      } else {
        setData((prev) => ({ ...prev, hasMore: false }));
      }
    } finally {
      setLoading(false);
    }
  }, [data, adjustflag, startDate, endDate, loading]);

  const option = useMemo(() => buildOption(data), [data]);

  return (
    <div className="rounded-lg border border-border bg-bg-panel p-4 flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold text-slate-100">
            日线K线{data.code ? ` - ${data.code}` : ''}
          </h3>
          <p className="text-xs text-muted mt-0.5">
            {data.records.length > 0
              ? `${data.records[0].tradeDate} ~ ${data.records[data.records.length - 1].tradeDate}，已载入 ${data.records.length} 根K线`
              : '请输入股票代码后搜索'}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => chartRef.current?.getEchartsInstance().dispatchAction({ type: 'dataZoom', zoom: 0.5 })} title="左移">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => chartRef.current?.getEchartsInstance().dispatchAction({ type: 'dataZoom', zoom: 2 })} title="右移">
            <ChevronRight className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" title="缩小">
            <ZoomOut className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" title="放大">
            <ZoomIn className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={loadOlder} disabled={loading || !data.hasMore}>
            {loading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : null}
            {data.hasMore ? '加载更早' : '已全部加载'}
          </Button>
        </div>
      </div>
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: 520 }}
        notMerge={false}
        lazyUpdate
        theme="dark"
      />
    </div>
  );
}

/**
 * 合併新舊技術指標數組（用於加載更早數據時拼接指標序列）。
 * @param older 較早的指標數據
 * @param newer 較新的指標數據
 * @param offset 偏移量（older 數據長度）
 * @returns 合併後的指標數據
 */
function mergeIndicators(
  older: CandlestickDto['indicators'],
  newer: CandlestickDto['indicators'],
  offset: number
): CandlestickDto['indicators'] {
  if (!older || !newer) return newer ?? older ?? null;
  const merge = (a: (number | null)[] | undefined, b: (number | null)[] | undefined) =>
    a && b ? [...a, ...b] : a ?? b ?? [];
  const maSeries: Record<string, (number | null)[]> = {};
  const keys = new Set([...Object.keys(older.maSeries), ...Object.keys(newer.maSeries)]);
  keys.forEach((k) => {
    maSeries[k] = merge(older.maSeries[k], newer.maSeries[k]);
  });
  return {
    maSeries,
    bollUpper: merge(older.bollUpper, newer.bollUpper),
    bollMiddle: merge(older.bollMiddle, newer.bollMiddle),
    bollLower: merge(older.bollLower, newer.bollLower),
    macdDif: merge(older.macdDif, newer.macdDif),
    macdDea: merge(older.macdDea, newer.macdDea),
    macdHist: merge(older.macdHist, newer.macdHist),
    kdjK: merge(older.kdjK, newer.kdjK),
    kdjD: merge(older.kdjD, newer.kdjD),
    kdjJ: merge(older.kdjJ, newer.kdjJ),
    rsi: merge(older.rsi, newer.rsi),
  };
}

/**
 * 構建 ECharts 配置項 — 將 K線數據和技術指標轉換為四面板圖表配置。
 * @param data K線數據（含記錄和指標）
 * @returns ECharts option 對象
 */
function buildOption(data: CandlestickDto): Record<string, unknown> {
  const records = data.records;
  const indicators = data.indicators;
  const dates = records.map((r) => r.tradeDate);
  const ohlc = records.map((r) => [r.open ?? 0, r.close ?? 0, r.low ?? 0, r.high ?? 0]);
  const volumes = records.map((r, i) => ({
    value: r.volume ?? 0,
    itemStyle: { color: (r.close ?? 0) >= (r.open ?? 0) ? '#22c55e' : '#ef4444' },
  }));

  const maLines: Record<string, unknown>[] = [];
  const maColors: Record<string, string> = { '5': '#f59e0b', '10': '#38bdf8', '20': '#a855f7', '60': '#ec4899', '120': '#64748b' };
  if (indicators?.maSeries) {
    for (const [period, values] of Object.entries(indicators.maSeries)) {
      maLines.push({
        name: `MA${period}`,
        type: 'line',
        data: values,
        smooth: false,
        symbol: 'none',
        lineStyle: { width: 1, color: maColors[period] || '#94a3b8' },
      });
    }
  }

  const bollSeries: Record<string, unknown>[] = [];
  if (indicators && indicators.bollUpper.length > 0) {
    bollSeries.push(
      { name: 'BOLL上轨', type: 'line', data: indicators.bollUpper, symbol: 'none', lineStyle: { width: 1, color: '#64748b' } },
      { name: 'BOLL中轨', type: 'line', data: indicators.bollMiddle, symbol: 'none', lineStyle: { width: 1, color: '#94a3b8' } },
      { name: 'BOLL下轨', type: 'line', data: indicators.bollLower, symbol: 'none', lineStyle: { width: 1, color: '#64748b' } }
    );
  }

  const macdHist = indicators?.macdHist ?? [];
  const macdDif = indicators?.macdDif ?? [];
  const macdDea = indicators?.macdDea ?? [];

  const kdjK = indicators?.kdjK ?? [];
  const kdjD = indicators?.kdjD ?? [];
  const kdjJ = indicators?.kdjJ ?? [];

  return {
    backgroundColor: 'transparent',
    animation: false,
    legend: { top: 0, textStyle: { color: '#94a3b8' }, data: [...maLines.map((l) => l.name), ...bollSeries.map((l) => l.name)] },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#0f172a',
      borderColor: '#1e293b',
      textStyle: { color: '#e2e8f0' },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: '8%', right: '4%', top: 40, height: '50%' },
      { left: '8%', right: '4%', top: '64%', height: '8%' },
      { left: '8%', right: '4%', top: '75%', height: '10%' },
      { left: '8%', right: '4%', top: '88%', height: '8%' },
    ],
    xAxis: [
      { type: 'category', data: dates, scale: true, boundaryGap: false, axisLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b' }, splitLine: { show: false } },
      { type: 'category', gridIndex: 1, data: dates, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#1e293b' } } },
      { type: 'category', gridIndex: 2, data: dates, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#1e293b' } } },
      { type: 'category', gridIndex: 3, data: dates, axisLabel: { color: '#64748b' }, axisLine: { lineStyle: { color: '#1e293b' } } },
    ],
    yAxis: [
      { scale: true, axisLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#16213a' } } },
      { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
      { gridIndex: 2, axisLabel: { color: '#64748b' }, splitLine: { show: false } },
      { gridIndex: 3, axisLabel: { color: '#64748b' }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2, 3], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1, 2, 3], top: '97%', start: 60, end: 100, height: 12, borderColor: '#1e293b', fillerColor: 'rgba(56,189,248,0.1)' },
    ],
    series: [
      { name: 'K线', type: 'candlestick', data: ohlc, itemStyle: { color: '#ef4444', color0: '#22c55e', borderColor: '#ef4444', borderColor0: '#22c55e' } },
      ...maLines,
      ...bollSeries,
      { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes },
      { name: 'MACD柱', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: macdHist.map((v) => ({ value: v ?? 0, itemStyle: { color: (v ?? 0) >= 0 ? '#ef4444' : '#22c55e' } })) },
      { name: 'DIF', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: macdDif, symbol: 'none', lineStyle: { width: 1, color: '#f59e0b' } },
      { name: 'DEA', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: macdDea, symbol: 'none', lineStyle: { width: 1, color: '#38bdf8' } },
      { name: 'K', type: 'line', xAxisIndex: 3, yAxisIndex: 3, data: kdjK, symbol: 'none', lineStyle: { width: 1, color: '#f59e0b' } },
      { name: 'D', type: 'line', xAxisIndex: 3, yAxisIndex: 3, data: kdjD, symbol: 'none', lineStyle: { width: 1, color: '#38bdf8' } },
      { name: 'J', type: 'line', xAxisIndex: 3, yAxisIndex: 3, data: kdjJ, symbol: 'none', lineStyle: { width: 1, color: '#a855f7' } },
    ],
  };
}
