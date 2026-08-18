/**
 * @file CandidateDetail 組件 — 選股候選詳情面板，
 * 展示選中股票的 K線圖和全部技術指標數值（MA、BOLL、MACD、KDJ、RSI 等）。
 */
'use client';

import { useMemo } from 'react';
import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { CandlestickChart } from '@/components/chart/CandlestickChart';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { api } from '@/lib/api';
import type { ScreenedStockDto } from '@/lib/api/types';
import { formatPercent, formatVolume, formatCurrency, describeCross, describeBoll } from '@/lib/format';

/**
 * CandidateDetail 組件 — 候選股票詳情面板。
 * @param stock 選中的股票數據，null 時顯示提示文字
 */
export function CandidateDetail({ stock }: { stock: ScreenedStockDto | null }) {
  // 根據選中股票構建 K線請求參數
  const chartParams = useMemo(() => {
    if (!stock) return null;
    const params = new URLSearchParams();
    params.set('code', stock.code);
    params.set('adjustflag', '3');
    params.set('limit', '120');
    return params;
  }, [stock]);

  const chartKey = chartParams ? `/chart/candlestick?${chartParams.toString()}` : null;
  const { data: chart, error: chartError, isLoading: chartLoading, mutate: reloadChart } = useSWR(
    chartKey,
    () => api.candlestick(chartParams!),
    { revalidateOnFocus: false, dedupingInterval: 30000 }
  );

  if (!stock) {
    return (
      <Card>
        <CardHeader><CardTitle>候选详情</CardTitle></CardHeader>
        <CardContent className="text-muted">点击结果表中的行查看详情</CardContent>
      </Card>
    );
  }

  const rows: [string, string][] = [
    ['代码', stock.code],
    ['日期', stock.tradeDate],
    ['收盘价', stock.closePrice.toFixed(2)],
    ['涨跌幅', formatPercent(stock.pctChange)],
    ['振幅', `${stock.amplitude.toFixed(2)}%`],
    ['换手率', `${stock.turn.toFixed(2)}%`],
    ['成交量', formatVolume(stock.volume)],
    ['成交额', formatCurrency(stock.amount)],
    ['MA5', stock.ma5?.toFixed(2) ?? '-'],
    ['MA10', stock.ma10?.toFixed(2) ?? '-'],
    ['MA20', stock.ma20?.toFixed(2) ?? '-'],
    ['MA60', stock.ma60?.toFixed(2) ?? '-'],
    ['MA120', stock.ma120?.toFixed(2) ?? '-'],
    ['量比', stock.volumeRatio?.toFixed(2) ?? '-'],
    ['20日收益', formatPercent(stock.return20)],
    ['60日收益', formatPercent(stock.return60)],
    ['120日收益', formatPercent(stock.return120)],
    ['RSI14', stock.rsi14?.toFixed(2) ?? '-'],
    ['K', stock.kValue?.toFixed(2) ?? '-'],
    ['D', stock.dValue?.toFixed(2) ?? '-'],
    ['J', stock.jValue?.toFixed(2) ?? '-'],
    ['KDJ信号', describeCross(stock.kdjCrossSignal)],
    ['DIF', stock.dif?.toFixed(4) ?? '-'],
    ['DEA', stock.dea?.toFixed(4) ?? '-'],
    ['MACD柱', stock.macdHist?.toFixed(4) ?? '-'],
    ['MACD信号', describeCross(stock.macdCrossSignal)],
    ['BOLL上轨', stock.bollUpper?.toFixed(2) ?? '-'],
    ['BOLL中轨', stock.bollMiddle?.toFixed(2) ?? '-'],
    ['BOLL下轨', stock.bollLower?.toFixed(2) ?? '-'],
    ['BOLL带宽', `${stock.bollWidth?.toFixed(2) ?? '-'}%`],
    ['BOLL%B', `${stock.bollPercentB?.toFixed(2) ?? '-'}%`],
    ['BOLL位置', describeBoll(stock.bollPosition)],
    ['综合评分', stock.score.toFixed(2)],
    ['ST', stock.isSt ? '是' : '否'],
  ];

  return (
    <div className="space-y-4">
      {/* K線圖 */}
      <Card>
        <CardHeader>
          <CardTitle>{stock.code} K线图</CardTitle>
        </CardHeader>
        <CardContent>
          {chartLoading && <ChartSkeleton />}
          {chartError && <ErrorState message={`K线图加载失败: ${chartError.message}`} onRetry={reloadChart} />}
          {chart && (
            <CandlestickChart
              initial={chart}
              adjustflag={3}
              startDate={null}
              endDate={null}
            />
          )}
        </CardContent>
      </Card>

      {/* 指標詳情 */}
      <Card>
        <CardHeader><CardTitle>{stock.code} 指标详情</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-1 text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-border-subtle py-1">
                <span className="text-muted">{k}</span>
                <span className="text-slate-200 tabular-nums">{v}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
