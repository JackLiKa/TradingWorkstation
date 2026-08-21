'use client';

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import { IndustryTreemap } from '@/components/industry/IndustryTreemap';
import { IndustryCapitalFlow } from '@/components/industry/IndustryCapitalFlow';
import { IndustryRisingFalling } from '@/components/industry/IndustryRisingFalling';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { Button } from '@/components/ui/Button';
import { Calendar, RefreshCw, TrendingUp, DollarSign, BarChart3 } from 'lucide-react';

/** 可視化類型 */
type ViewType = 'heatmap' | 'capital' | 'risingFalling';

const VIEWS: { key: ViewType; label: string; icon: typeof TrendingUp }[] = [
  { key: 'heatmap', label: '行業熱力圖', icon: TrendingUp },
  { key: 'capital', label: '資金流向', icon: DollarSign },
  { key: 'risingFalling', label: '漲跌家數', icon: BarChart3 },
];

export default function IndustryPage() {
  const [view, setView] = useState<ViewType>('heatmap');
  const [tradeDate, setTradeDate] = useState<string>('');

  const { data, error, isLoading, mutate } = useSWR(
    `/stock/industry-daily${tradeDate ? `?tradeDate=${tradeDate}` : ''}`,
    () => api.industryDaily(tradeDate || undefined),
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  const latestDate = useMemo(() => {
    if (!data || data.length === 0) return '';
    return data[0].tradeDate;
  }, [data]);

  const title = `行業分析 ${latestDate ? `(${latestDate})` : ''}`;

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">{title}</h1>
          <p className="text-sm text-muted mt-1">基於 industry_daily 表的行業日聚合數據</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-md border border-border bg-bg-panel px-3 py-2">
            <Calendar className="w-4 h-4 text-slate-400" />
            <input
              type="date"
              value={tradeDate}
              onChange={(e) => setTradeDate(e.target.value)}
              className="bg-transparent text-sm text-slate-100 outline-none"
            />
          </div>
          <Button onClick={() => mutate()} size="sm" variant="outline">
            <RefreshCw className="w-4 h-4 mr-1" />
            刷新
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {VIEWS.map(({ key, label, icon: Icon }) => {
          const active = view === key;
          return (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? 'bg-accent/10 text-accent'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          );
        })}
      </div>

      {isLoading && <Skeleton className="h-[500px]" />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && data && data.length === 0 && (
        <div className="text-center py-20 text-muted">暫無行業聚合數據</div>
      )}
      {!isLoading && !error && data && data.length > 0 && (
        <>
          {view === 'heatmap' && <IndustryTreemap data={data} />}
          {view === 'capital' && <IndustryCapitalFlow data={data} />}
          {view === 'risingFalling' && <IndustryRisingFalling data={data} />}
        </>
      )}
    </div>
  );
}
