/**
 * @file BacktestStatisticsPanel 組件 — 回測統計指標面板，
 * 以卡片網格展示總收益、年化、基準、超額、最大回撤、夏普等關鍵指標。
 */
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import type { BacktestStatistics } from '@/lib/api/types';

/**
 * BacktestStatisticsPanel 組件 — 回測統計指標面板。
 * @param stats 回測統計數據
 */
export function BacktestStatisticsPanel({ stats }: { stats: BacktestStatistics }) {
  const items: [string, string, string][] = [
    ['策略总收益', `${stats.totalReturn}%`, stats.totalReturn >= 0 ? 'text-up' : 'text-down'],
    ['年化收益', `${stats.annualReturn}%`, stats.annualReturn >= 0 ? 'text-up' : 'text-down'],
    ['基准收益', `${stats.benchmarkReturn}%`, stats.benchmarkReturn >= 0 ? 'text-up' : 'text-down'],
    ['超额收益', `${stats.excessReturn}%`, stats.excessReturn >= 0 ? 'text-up' : 'text-down'],
    ['最大回撤', `${stats.maxDrawdown}%`, 'text-down'],
    ['夏普比率', stats.sharpe.toFixed(2), 'text-slate-200'],
    ['调仓次数', String(stats.rebalanceCount), 'text-slate-200'],
    ['总交易笔数', String(stats.totalTrades), 'text-slate-200'],
  ];
  return (
    <Card>
      <CardHeader><CardTitle>回测统计</CardTitle></CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {items.map(([label, value, cls]) => (
            <div key={label} className="flex flex-col gap-1 border border-border rounded-md p-3 bg-bg-card">
              <span className="text-xs text-muted">{label}</span>
              <span className={`text-xl font-bold tabular-nums ${cls}`}>{value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
