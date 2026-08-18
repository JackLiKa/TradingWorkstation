/**
 * @file ScreenerResultTable 組件 — 選股結果表格，
 * 展示候選股票的評分、價格、漲跌幅、技術指標和交叉信號等信息。
 */
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import type { ScreenedStockDto } from '@/lib/api/types';
import { formatPercent, formatVolume, formatCurrency, pctClass, describeCross, describeBoll } from '@/lib/format';

/** ScreenerResultTable 組件屬性 */
interface Props {
  /** 候選股票列表 */
  candidates: ScreenedStockDto[];
  /** 點擊行回調（傳入選中的股票數據） */
  onSelect?: (stock: ScreenedStockDto) => void;
  /** 當前選中的股票代碼 */
  selected?: string | null;
}

/**
 * ScreenerResultTable 組件 — 選股結果表格。
 * @param candidates 候選股票列表
 * @param onSelect 點擊行回調
 * @param selected 當前選中代碼
 */
export function ScreenerResultTable({ candidates, onSelect, selected }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>选股结果</CardTitle>
        <span className="text-xs text-muted">{candidates.length} 条</span>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-auto max-h-[520px]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-bg-panel">
              <tr className="border-b border-border text-xs text-muted">
                <th className="text-left px-3 py-2 font-normal">代码</th>
                <th className="text-right px-3 py-2 font-normal">评分</th>
                <th className="text-right px-3 py-2 font-normal">收盘价</th>
                <th className="text-right px-3 py-2 font-normal">涨跌幅</th>
                <th className="text-right px-3 py-2 font-normal">换手率</th>
                <th className="text-right px-3 py-2 font-normal">量比</th>
                <th className="text-right px-3 py-2 font-normal">20日</th>
                <th className="text-right px-3 py-2 font-normal">60日</th>
                <th className="text-right px-3 py-2 font-normal">RSI</th>
                <th className="text-center px-3 py-2 font-normal">MACD</th>
                <th className="text-center px-3 py-2 font-normal">KDJ</th>
                <th className="text-center px-3 py-2 font-normal">BOLL</th>
              </tr>
            </thead>
            <tbody>
              {candidates.length === 0 ? (
                <tr>
                  <td colSpan={12} className="px-3 py-6 text-center text-muted">暂无命中股票</td>
                </tr>
              ) : (
                candidates.map((s) => (
                  <tr
                    key={s.code}
                    onClick={() => onSelect?.(s)}
                    className={`border-b border-border-subtle hover:bg-bg-hover cursor-pointer ${selected === s.code ? 'bg-accent/5' : ''}`}
                  >
                    <td className="px-3 py-1.5 font-mono text-slate-200">{s.code}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-semibold text-accent">{s.score.toFixed(2)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-200">{s.closePrice.toFixed(2)}</td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${pctClass(s.pctChange)}`}>{formatPercent(s.pctChange)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{s.turn.toFixed(2)}%</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{s.volumeRatio?.toFixed(2) ?? '-'}</td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${pctClass(s.return20)}`}>{formatPercent(s.return20)}</td>
                    <td className={`px-3 py-1.5 text-right tabular-nums ${pctClass(s.return60)}`}>{formatPercent(s.return60)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{s.rsi14?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-1.5 text-center">
                      <Badge variant={s.macdCrossSignal === 'golden_cross' ? 'danger' : s.macdCrossSignal === 'death_cross' ? 'success' : 'default'}>
                        {describeCross(s.macdCrossSignal)}
                      </Badge>
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      <Badge variant={s.kdjCrossSignal === 'golden_cross' ? 'danger' : s.kdjCrossSignal === 'death_cross' ? 'success' : 'default'}>
                        {describeCross(s.kdjCrossSignal)}
                      </Badge>
                    </td>
                    <td className="px-3 py-1.5 text-center text-xs text-slate-300">{describeBoll(s.bollPosition)}</td>
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
