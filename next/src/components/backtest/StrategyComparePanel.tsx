/**
 * @file StrategyComparePanel 組件 — 策略對比面板，
 * 以表格形式並排展示多個策略的統計指標，自動標記每個指標的最佳值。
 */
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { X } from 'lucide-react';
import type { SavedStrategyDetailDto } from '@/lib/api/types';

/** StrategyComparePanel 組件屬性 */
interface StrategyComparePanelProps {
  /** 待對比的策略詳情列表 */
  strategies: SavedStrategyDetailDto[];
  /** 關閉對比面板回調 */
  onClose: () => void;
}

/**
 * StrategyComparePanel 組件 — 策略對比面板。
 * 對比 8 項統計指標 + 4 項配置摘要，最佳值以 ★ 標記。
 * @param strategies 策略列表
 * @param onClose 關閉回調
 */
export function StrategyComparePanel({ strategies, onClose }: StrategyComparePanelProps) {
  if (strategies.length === 0) return null;

  // 對比指標
  const metrics: { key: string; label: string; format: (v: number) => string; color?: (v: number) => string }[] = [
    { key: 'totalReturn', label: '总收益(%)', format: (v) => v.toFixed(2), color: (v) => v >= 0 ? 'text-up' : 'text-down' },
    { key: 'annualReturn', label: '年化(%)', format: (v) => v.toFixed(2), color: (v) => v >= 0 ? 'text-up' : 'text-down' },
    { key: 'benchmarkReturn', label: '基准(%)', format: (v) => v.toFixed(2), color: (v) => v >= 0 ? 'text-up' : 'text-down' },
    { key: 'excessReturn', label: '超额(%)', format: (v) => v.toFixed(2), color: (v) => v >= 0 ? 'text-up' : 'text-down' },
    { key: 'maxDrawdown', label: '最大回撤(%)', format: (v) => v.toFixed(2), color: () => 'text-down' },
    { key: 'sharpe', label: '夏普', format: (v) => v.toFixed(2), color: (v) => v >= 1 ? 'text-up' : v >= 0 ? 'text-slate-200' : 'text-down' },
    { key: 'rebalanceCount', label: '调仓次数', format: (v) => String(Math.round(v)), color: () => 'text-slate-200' },
    { key: 'totalTrades', label: '交易笔数', format: (v) => String(Math.round(v)), color: () => 'text-slate-200' },
  ];

  // 找每個指標的最佳值
  const bestValues: Record<string, number> = {};
  for (const m of metrics) {
    const values = strategies
      .map((s) => s.result?.statistics?.[m.key as keyof typeof s.result.statistics] as number)
      .filter((v) => v != null && !isNaN(v));
    if (values.length === 0) continue;
    if (m.key === 'maxDrawdown') {
      bestValues[m.key] = Math.min(...values); // 回撤越小越好
    } else if (m.key === 'sharpe' || m.key === 'totalReturn' || m.key === 'annualReturn' || m.key === 'excessReturn') {
      bestValues[m.key] = Math.max(...values); // 越大越好
    } else {
      bestValues[m.key] = Math.max(...values);
    }
  }

  return (
    <Card className="border-accent/30">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          策略對比
          <span className="text-xs font-normal text-muted">({strategies.length} 个策略)</span>
        </CardTitle>
        <Button size="sm" variant="ghost" onClick={onClose}>
          <X className="w-4 h-4" />
        </Button>
      </CardHeader>
      <CardContent className="overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2 px-3 text-xs text-muted font-normal">指标</th>
              {strategies.map((s) => (
                <th key={s.id} className="text-right py-2 px-3 text-xs text-slate-200 font-medium">
                  {s.name}
                  <div className="text-[10px] text-muted font-normal">
                    {s.config.startDate} ~ {s.config.endDate}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metrics.map((m) => (
              <tr key={m.key} className="border-b border-border-subtle">
                <td className="py-2 px-3 text-xs text-muted">{m.label}</td>
                {strategies.map((s) => {
                  const raw = s.result?.statistics?.[m.key as keyof typeof s.result.statistics] as number;
                  const value = raw != null && !isNaN(raw) ? raw : null;
                  const isBest = value != null && bestValues[m.key] === value;
                  return (
                    <td
                      key={s.id}
                      className={`text-right py-2 px-3 tabular-nums ${
                        value == null ? 'text-muted' : m.color ? m.color(value) : 'text-slate-200'
                      } ${isBest ? 'font-bold' : ''}`}
                    >
                      {value == null ? '-' : m.format(value)}
                      {isBest && value != null && <span className="ml-1 text-[10px] text-accent">★</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
            {/* 配置摘要 */}
            <tr className="border-b border-border-subtle">
              <td className="py-2 px-3 text-xs text-muted">最大持仓</td>
              {strategies.map((s) => (
                <td key={s.id} className="text-right py-2 px-3 text-slate-300 tabular-nums">{s.config.maxPositions}</td>
              ))}
            </tr>
            <tr className="border-b border-border-subtle">
              <td className="py-2 px-3 text-xs text-muted">调仓间隔</td>
              {strategies.map((s) => (
                <td key={s.id} className="text-right py-2 px-3 text-slate-300 tabular-nums">{s.config.rebalanceInterval}日</td>
              ))}
            </tr>
            <tr className="border-b border-border-subtle">
              <td className="py-2 px-3 text-xs text-muted">持有期</td>
              {strategies.map((s) => (
                <td key={s.id} className="text-right py-2 px-3 text-slate-300 tabular-nums">{s.config.holdingPeriod}日</td>
              ))}
            </tr>
            <tr>
              <td className="py-2 px-3 text-xs text-muted">初始资金</td>
              {strategies.map((s) => (
                <td key={s.id} className="text-right py-2 px-3 text-slate-300 tabular-nums">
                  {s.config.initialCapital.toLocaleString()}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
