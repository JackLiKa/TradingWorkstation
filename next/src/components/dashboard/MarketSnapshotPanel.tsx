'use client';

/**
 * @file MarketSnapshotPanel — 行情預計算快照面板。
 *
 * 直接加載 market_analysis_snapshot 表中的預計算數據，
 * 無需實時計算，加載速度從數秒降至毫秒級。
 *
 * 支持歷史快照回看（選擇不同交易日的快照）。
 */

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { Activity, TrendingUp, TrendingDown, Gauge, RefreshCw, Calendar, Database } from 'lucide-react';

interface IndexData {
  code: string;
  close: number;
  pctChg: number;
  amount: number;
}

interface BreadthData {
  rising: number;
  falling: number;
  flat: number;
  total: number;
  limit_up: number;
  limit_down: number;
}

interface SummaryData {
  stock_count: number;
  total_amount: number;
  avg_pct_chg: number;
}

interface IndustryProsperityItem {
  industry: string;
  avg_pct_chg: number;
  total_amount: number;
  prosperity_index: number;
  grade: string;
  momentum_score: number;
  capital_score: number;
  activity_score: number;
  breadth_score: number;
}

interface RotationItem {
  industry: string;
  short_term_avg: number;
  long_term_avg: number;
  momentum_diff: number;
  signal: string;
}

interface SnapshotData {
  found: boolean;
  trade_date?: string;
  computed_at?: string;
  market_overview?: {
    indices: IndexData[];
    breadth: BreadthData;
    summary: SummaryData;
  };
  industry_prosperity?: IndustryProsperityItem[];
  rotation_signals?: RotationItem[];
  market_breadth?: Array<{
    date: string;
    rising: number;
    falling: number;
    total: number;
    avg_pct_chg: number;
    total_amount: number;
  }>;
  message?: string;
}

const INDEX_NAMES: Record<string, string> = {
  'sh.000001': '上證指數',
  'sz.399001': '深證成指',
  'sz.399006': '創業板指',
  'sh.000300': '滬深300',
  'sh.000016': '上證50',
  'sh.000688': '科創50',
};

export function MarketSnapshotPanel() {
  const [selectedDate, setSelectedDate] = useState<string>('');

  // 獲取可用日期列表
  const { data: datesData } = useSWR(
    '/snapshot/dates',
    () => api.snapshotDates('market_overview', 20),
    { revalidateOnFocus: false, dedupingInterval: 300000 }
  );

  // 獲取快照數據
  const snapshotKey = `/snapshot${selectedDate ? `?tradeDate=${selectedDate}` : ''}`;
  const { data: snapshot, error, isLoading, mutate } = useSWR<SnapshotData>(
    snapshotKey,
    () => api.allSnapshots(selectedDate || undefined) as unknown as Promise<SnapshotData>,
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  const availableDates = useMemo(() => {
    return (datesData as { dates: string[] })?.dates || [];
  }, [datesData]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm text-muted">
          <Database className="w-4 h-4" />
          <span>正在載入預計算快照...</span>
        </div>
        <ChartSkeleton />
      </div>
    );
  }

  if (error) {
    return <ErrorState message="快照載入失敗" onRetry={() => mutate()} />;
  }

  if (!snapshot || !snapshot.found) {
    return (
      <div className="rounded-lg border border-border p-6 text-center">
        <Database className="w-8 h-8 text-muted mx-auto mb-2" />
        <p className="text-sm text-muted">{snapshot?.message || '暫無預計算快照數據'}</p>
        <p className="text-xs text-muted mt-1">
          快照會在數據更新後自動生成。運行 ingestion 腳本後即可使用。
        </p>
      </div>
    );
  }

  const overview = snapshot.market_overview;
  const prosperity = snapshot.industry_prosperity || [];
  const rotation = snapshot.rotation_signals || [];
  const breadthHistory = snapshot.market_breadth || [];

  return (
    <div className="space-y-4">
      {/* 標題列 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="w-5 h-5 text-accent" />
          <h2 className="text-lg font-semibold text-slate-100">行情預計算快照</h2>
          <span className="text-xs text-muted">
            {snapshot.trade_date} · 計算於 {snapshot.computed_at?.slice(11, 19)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {availableDates.length > 0 && (
            <select
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="text-xs bg-bg-hover border border-border rounded px-2 py-1 text-slate-200"
            >
              <option value="">最新交易日</option>
              {availableDates.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          )}
          <RefreshButton onClick={() => mutate()} />
        </div>
      </div>

      {/* 市場概覽 */}
      {overview && (
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-accent" />
            <h3 className="text-sm font-semibold text-slate-200">市場概覽</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {overview.indices.map((idx) => (
              <div key={idx.code} className="bg-bg-hover rounded p-2">
                <div className="text-xs text-muted">{INDEX_NAMES[idx.code] || idx.code}</div>
                <div className="text-lg font-bold text-slate-100">{idx.close.toFixed(2)}</div>
                <div className={`text-xs flex items-center gap-1 ${idx.pctChg >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {idx.pctChg >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {idx.pctChg >= 0 ? '+' : ''}{idx.pctChg.toFixed(2)}%
                </div>
              </div>
            ))}
          </div>
          {overview.breadth && (
            <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
              <div className="text-center">
                <span className="text-red-400 font-bold">{overview.breadth.rising}</span>
                <span className="text-muted ml-1">上漲</span>
              </div>
              <div className="text-center">
                <span className="text-green-400 font-bold">{overview.breadth.falling}</span>
                <span className="text-muted ml-1">下跌</span>
              </div>
              <div className="text-center">
                <span className="text-slate-300 font-bold">{overview.breadth.total}</span>
                <span className="text-muted ml-1">總計</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 行業景氣度 TOP 10 */}
      {prosperity.length > 0 && (
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <Gauge className="w-4 h-4 text-accent" />
            <h3 className="text-sm font-semibold text-slate-200">行業景氣度 TOP 10</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-border">
                  <th className="text-left py-1 px-2">排名</th>
                  <th className="text-left py-1 px-2">行業</th>
                  <th className="text-right py-1 px-2">景氣度</th>
                  <th className="text-right py-1 px-2">等級</th>
                  <th className="text-right py-1 px-2">動量</th>
                  <th className="text-right py-1 px-2">資金</th>
                  <th className="text-right py-1 px-2">活躍度</th>
                  <th className="text-right py-1 px-2">廣度</th>
                </tr>
              </thead>
              <tbody>
                {prosperity.slice(0, 10).map((item, i) => (
                  <tr key={item.industry} className="border-b border-border/50">
                    <td className="py-1 px-2 text-muted">{i + 1}</td>
                    <td className="py-1 px-2 text-slate-200">{item.industry}</td>
                    <td className="py-1 px-2 text-right font-bold text-accent">{item.prosperity_index.toFixed(1)}</td>
                    <td className="py-1 px-2 text-right">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                        item.grade === '優' ? 'bg-red-500/20 text-red-400' :
                        item.grade === '良' ? 'bg-orange-500/20 text-orange-400' :
                        item.grade === '中' ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-green-500/20 text-green-400'
                      }`}>{item.grade}</span>
                    </td>
                    <td className="py-1 px-2 text-right text-slate-300">{item.momentum_score.toFixed(1)}</td>
                    <td className="py-1 px-2 text-right text-slate-300">{item.capital_score.toFixed(1)}</td>
                    <td className="py-1 px-2 text-right text-slate-300">{item.activity_score.toFixed(1)}</td>
                    <td className="py-1 px-2 text-right text-slate-300">{item.breadth_score.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 輪動信號 */}
      {rotation.length > 0 && (
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <RefreshCw className="w-4 h-4 text-accent" />
            <h3 className="text-sm font-semibold text-slate-200">行業輪動信號</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {rotation.slice(0, 8).map((item) => (
              <div key={item.industry} className="bg-bg-hover rounded p-2">
                <div className="text-xs text-slate-200 truncate">{item.industry}</div>
                <div className={`text-xs font-semibold ${
                  item.signal === '加速上漲' ? 'text-red-400' :
                  item.signal === '溫和上行' ? 'text-orange-400' :
                  item.signal === '溫和下行' ? 'text-green-400' :
                  'text-green-300'
                }`}>{item.signal}</div>
                <div className="text-[10px] text-muted">
                  短期 {item.short_term_avg >= 0 ? '+' : ''}{item.short_term_avg.toFixed(2)}% / 長期 {item.long_term_avg >= 0 ? '+' : ''}{item.long_term_avg.toFixed(2)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 市場廣度歷史 */}
      {breadthHistory.length > 0 && (
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="w-4 h-4 text-accent" />
            <h3 className="text-sm font-semibold text-slate-200">市場廣度（最近 {breadthHistory.length} 天）</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-border">
                  <th className="text-left py-1 px-2">日期</th>
                  <th className="text-right py-1 px-2">上漲</th>
                  <th className="text-right py-1 px-2">下跌</th>
                  <th className="text-right py-1 px-2">總計</th>
                  <th className="text-right py-1 px-2">平均漲跌</th>
                </tr>
              </thead>
              <tbody>
                {breadthHistory.map((d) => (
                  <tr key={d.date} className="border-b border-border/50">
                    <td className="py-1 px-2 text-slate-200">{d.date}</td>
                    <td className="py-1 px-2 text-right text-red-400">{d.rising}</td>
                    <td className="py-1 px-2 text-right text-green-400">{d.falling}</td>
                    <td className="py-1 px-2 text-right text-slate-300">{d.total}</td>
                    <td className={`py-1 px-2 text-right ${d.avg_pct_chg >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {d.avg_pct_chg >= 0 ? '+' : ''}{d.avg_pct_chg.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
