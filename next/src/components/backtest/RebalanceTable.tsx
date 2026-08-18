/**
 * @file RebalanceTable 組件 — 調倉明細表格，
 * 按日期降序展示每次調倉的買入、賣出和持有股票列表。
 */
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import type { RebalanceEvent } from '@/lib/api/types';

/**
 * RebalanceTable 組件 — 調倉明細表格。
 * @param rebalances 調倉事件列表
 */
export function RebalanceTable({ rebalances }: { rebalances: RebalanceEvent[] }) {
  // 最新操作優先（日期降序）
  const sorted = [...rebalances].sort((a, b) => b.date.localeCompare(a.date));
  return (
    <Card>
      <CardHeader>
        <CardTitle>调仓明细</CardTitle>
        <span className="text-xs text-muted">{rebalances.length} 次</span>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-auto max-h-80">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-bg-panel">
              <tr className="border-b border-border text-xs text-muted">
                <th className="text-left px-3 py-2 font-normal">日期</th>
                <th className="text-left px-3 py-2 font-normal">买入</th>
                <th className="text-left px-3 py-2 font-normal">卖出</th>
                <th className="text-left px-3 py-2 font-normal">持有</th>
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 ? (
                <tr><td colSpan={4} className="px-3 py-6 text-center text-muted">暂无调仓记录</td></tr>
              ) : (
                sorted.map((r, i) => (
                  <tr key={i} className="border-b border-border-subtle">
                    <td className="px-3 py-1.5 text-slate-200">{r.date}</td>
                    <td className="px-3 py-1.5 font-mono text-xs text-up">{r.bought.join(', ') || '-'}</td>
                    <td className="px-3 py-1.5 font-mono text-xs text-down">{r.sold.join(', ') || '-'}</td>
                    <td className="px-3 py-1.5 font-mono text-xs text-slate-300">{r.held.join(', ') || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
