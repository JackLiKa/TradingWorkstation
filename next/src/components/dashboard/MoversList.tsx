/**
 * @file MoversList 組件 — 最新波動列表，按 |漲跌幅| 排序展示熱門股票。
 */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import type { HotSymbolDto } from '@/lib/api/types';
import { formatPercent, formatVolume, pctClass } from '@/lib/format';

/**
 * MoversList 組件 — 以表格形式展示漲跌幅最大的股票列表。
 * @param movers 熱門股票數據數組
 * @param onSelect 點擊行回調（傳入股票代碼）
 */
export function MoversList({ movers, onSelect }: { movers: HotSymbolDto[]; onSelect?: (code: string) => void }) {
  const safeMovers = movers ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>最新波动</CardTitle>
        <span className="text-xs text-muted">最新交易日 |涨跌幅| 排序</span>
      </CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-muted">
              <th className="text-left px-4 py-2 font-normal">代码</th>
              <th className="text-right px-4 py-2 font-normal">收盘价</th>
              <th className="text-right px-4 py-2 font-normal">涨跌幅</th>
              <th className="text-right px-4 py-2 font-normal">成交量</th>
            </tr>
          </thead>
          <tbody>
            {safeMovers.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted">暂无数据</td>
              </tr>
            ) : (
              safeMovers.map((m) => (
                <tr
                  key={m.code}
                  className={`border-b border-border-subtle hover:bg-bg-hover ${onSelect ? 'cursor-pointer' : ''}`}
                  onClick={() => onSelect?.(m.code)}
                >
                  <td className="px-4 py-2 font-mono text-slate-200">{m.code}</td>
                  <td className="px-4 py-2 text-right tabular-nums text-slate-200">
                    {m.closePrice?.toFixed(2) ?? '-'}
                  </td>
                  <td className={`px-4 py-2 text-right tabular-nums ${pctClass(m.pctChange)}`}>
                    {formatPercent(m.pctChange)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-slate-300">
                    {formatVolume(m.volume)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
