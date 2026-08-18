/**
 * @file StockTable 組件 — 日線數據表格，展示股票行情的 OHLCV 和漲跌幅等信息。
 */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import type { StockDailyDto } from '@/lib/api/types';
import { formatPercent, formatVolume, formatCurrency, pctClass } from '@/lib/format';

/**
 * StockTable 組件 — 以表格形式展示日線行情數據。
 * @param records 日線數據數組
 */
export function StockTable({ records }: { records: StockDailyDto[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>日线数据</CardTitle>
        <span className="text-xs text-muted">{records.length} 条</span>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-auto max-h-[420px]">
          <table className="w-full min-w-[800px] text-sm">
            <thead className="sticky top-0 bg-bg-panel">
              <tr className="border-b border-border text-xs text-muted">
                <th className="text-left px-3 py-2 font-normal">代码</th>
                <th className="text-left px-3 py-2 font-normal">日期</th>
                <th className="text-right px-3 py-2 font-normal">开盘</th>
                <th className="text-right px-3 py-2 font-normal">最高</th>
                <th className="text-right px-3 py-2 font-normal">最低</th>
                <th className="text-right px-3 py-2 font-normal">收盘</th>
                <th className="text-right px-3 py-2 font-normal">涨跌幅</th>
                <th className="text-right px-3 py-2 font-normal">成交量</th>
                <th className="text-right px-3 py-2 font-normal">成交额</th>
                <th className="text-right px-3 py-2 font-normal">换手率</th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-3 py-6 text-center text-muted">暂无数据</td>
                </tr>
              ) : (
                records.map((r, i) => (
                  <tr key={`${r.code}-${r.tradeDate}-${i}`} className="border-b border-border-subtle hover:bg-bg-hover">
                    <td className="px-3 py-1.5 font-mono text-slate-200">{r.code}</td>
                    <td className="px-3 py-1.5 text-slate-300">{r.tradeDate}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{r.open?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{r.high?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{r.low?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-200">{r.close?.toFixed(2) ?? '-'}</td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${pctClass(r.pctChange)}`}>
                      {formatPercent(r.pctChange)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{formatVolume(r.volume)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{formatCurrency(r.amount)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{r.turn?.toFixed(2) ?? '-'}%</td>
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
