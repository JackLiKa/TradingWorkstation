'use client';

import { useState, useMemo } from 'react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import { IndustryTreemap } from '@/components/industry/IndustryTreemap';
import { IndustryCapitalFlow } from '@/components/industry/IndustryCapitalFlow';
import { IndustryRisingFalling } from '@/components/industry/IndustryRisingFalling';
import { IndustryTrendChart } from '@/components/industry/IndustryTrendChart';
import { RotationHistoryChart } from '@/components/industry/RotationHistoryChart';
import { IndustryCorrelationHeatmap } from '@/components/industry/IndustryCorrelationHeatmap';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { Button } from '@/components/ui/Button';
import { Calendar, RefreshCw, TrendingUp, DollarSign, BarChart3, Activity, RotateCcw, BarChart2, Newspaper, RefreshCcw, Grid3x3 } from 'lucide-react';
import type { IndustryDailyDto, IndexDailyDto } from '@/lib/api/types';
import { agentApi, type IndustryNewsItem } from '@/lib/api/agent';

/** 可視化類型 */
type ViewType = 'heatmap' | 'capital' | 'risingFalling' | 'trend' | 'rotation' | 'correlation';

const VIEWS: { key: ViewType; label: string; icon: typeof TrendingUp }[] = [
  { key: 'heatmap', label: '行業熱力圖', icon: TrendingUp },
  { key: 'capital', label: '資金流向', icon: DollarSign },
  { key: 'risingFalling', label: '漲跌家數', icon: BarChart3 },
  { key: 'trend', label: '行業走勢', icon: Activity },
  { key: 'rotation', label: '輪動信號', icon: RefreshCcw },
  { key: 'correlation', label: '相關性矩陣', icon: Grid3x3 },
];

function formatDateInput(d: Date) {
  return d.toISOString().slice(0, 10);
}

export default function IndustryPage() {
  const [view, setView] = useState<ViewType>('heatmap');
  const [tradeDate, setTradeDate] = useState<string>('');

  const dailyKey = `/stock/industry-daily${tradeDate ? `?tradeDate=${tradeDate}` : ''}`;
  const {
    data: daily,
    error: dailyError,
    isLoading: dailyLoading,
    mutate: mutateDaily,
    isValidating: dailyValidating,
  } = useSWR(dailyKey, () => api.industryDaily(tradeDate || undefined), {
    revalidateOnFocus: false,
    dedupingInterval: 60000,
  });

  const latestDate = useMemo(() => {
    if (!daily || daily.length === 0) return '';
    return daily[0].tradeDate;
  }, [daily]);

  const [selectedIndustry, setSelectedIndustry] = useState<string>('');
  const [rangeEnd, setRangeEnd] = useState<string>(formatDateInput(new Date()));
  const [rangeStart, setRangeStart] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return formatDateInput(d);
  });

  const trendKey =
    view === 'trend' && selectedIndustry
      ? `/stock/industry-daily/range?industry=${encodeURIComponent(selectedIndustry)}&start=${rangeStart}&end=${rangeEnd}`
      : null;
  const {
    data: trendData,
    error: trendError,
    isLoading: trendLoading,
    mutate: mutateTrend,
    isValidating: trendValidating,
  } = useSWR<IndustryDailyDto[]>(trendKey, () => api.industryDailyRange(selectedIndustry, rangeStart, rangeEnd), {
    revalidateOnFocus: false,
    dedupingInterval: 60000,
  });

  // 載入該行業的相關新聞（用於走勢圖上疊加標記）
  const newsKey =
    view === 'trend' && selectedIndustry
      ? `/api/agent/news/search?keyword=${encodeURIComponent(selectedIndustry)}&page_size=15`
      : null;
  const {
    data: newsData,
    error: newsError,
    isLoading: newsLoading,
  } = useSWR<{ keyword: string; news: IndustryNewsItem[] }>(newsKey, () => agentApi.searchNews(selectedIndustry, 15), {
    revalidateOnFocus: false,
    dedupingInterval: 300_000,
  });

  // 載入大盤基準指數（上證綜指）用於疊加對比
  const benchmarkDays = useMemo(() => {
    const start = new Date(rangeStart);
    const end = new Date(rangeEnd);
    const diff = Math.max(1, Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 10);
    return diff;
  }, [rangeStart, rangeEnd]);
  const benchmarkKey =
    view === 'trend' && selectedIndustry
      ? `/stock/index-history?code=sh.000001&days=${benchmarkDays}`
      : null;
  const {
    data: benchmarkData,
  } = useSWR<IndexDailyDto[]>(benchmarkKey, () => api.indexHistory('sh.000001', benchmarkDays), {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });

  const industries = useMemo(() => {
    if (!daily) return [];
    return daily.map((d) => d.industry);
  }, [daily]);

  const summary = useMemo(() => {
    if (!daily || daily.length === 0) return null;
    const totalAmount = daily.reduce((sum, d) => sum + (d.totalAmount ?? 0), 0);
    const avgPct = daily.reduce((sum, d) => sum + (d.avgPctChg ?? 0), 0) / daily.length;
    const top = daily[0];
    return { totalAmount, avgPct, top, count: daily.length };
  }, [daily]);

  const title = `行業分析 ${latestDate ? `(${latestDate})` : ''}`;

  const renderChart = () => {
    if (dailyLoading) return <ChartSkeleton />;
    if (dailyError) return <ErrorState message={String(dailyError)} onRetry={() => mutateDaily()} />;
    if (!daily || daily.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-muted rounded-lg border border-border bg-bg-panel">
          <BarChart2 className="w-12 h-12 mb-3 opacity-40" />
          <p>暫無行業聚合數據</p>
          <Button onClick={() => mutateDaily()} size="sm" variant="outline" className="mt-4">
            <RotateCcw className="w-4 h-4 mr-1" />
            重試
          </Button>
        </div>
      );
    }
    if (view === 'heatmap') return <IndustryTreemap data={daily} />;
    if (view === 'capital') return <IndustryCapitalFlow data={daily} />;
    if (view === 'risingFalling') return <IndustryRisingFalling data={daily} />;
    if (view === 'rotation') return <RotationHistoryChart />;
    if (view === 'correlation') return <IndustryCorrelationHeatmap rangeStart={rangeStart} rangeEnd={rangeEnd} />;
    return null;
  };

  const renderTrend = () => {
    if (!selectedIndustry) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-muted rounded-lg border border-border bg-bg-panel">
          <TrendingUp className="w-12 h-12 mb-3 opacity-40" />
          <p>請先選擇一個行業以查看歷史走勢</p>
        </div>
      );
    }
    if (trendLoading) return <ChartSkeleton />;
    if (trendError) return <ErrorState message={String(trendError)} onRetry={() => mutateTrend()} />;
    if (!trendData || trendData.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-muted rounded-lg border border-border bg-bg-panel">
          <BarChart2 className="w-12 h-12 mb-3 opacity-40" />
          <p>該行業在選定區間內無數據</p>
          <Button onClick={() => mutateTrend()} size="sm" variant="outline" className="mt-4">
            <RotateCcw className="w-4 h-4 mr-1" />
            重試
          </Button>
        </div>
      );
    }
    return <IndustryTrendChart data={trendData} news={newsData?.news ?? []} benchmark={benchmarkData ?? []} benchmarkLabel="上證綜指" />;
  };

  return (
    <div className="space-y-4 p-4 md:p-6 max-w-7xl mx-auto">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">{title}</h1>
          <p className="text-sm text-muted mt-1">基於 industry_daily 表的行業日聚合數據</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-md border border-border bg-bg-panel px-3 py-2">
            <Calendar className="w-4 h-4 text-slate-400" />
            <input
              type="date"
              value={tradeDate}
              onChange={(e) => setTradeDate(e.target.value)}
              className="bg-transparent text-sm text-slate-100 outline-none"
            />
          </div>
          <Button onClick={() => mutateDaily()} size="sm" variant="outline" disabled={dailyValidating}>
            <RefreshCw className={`w-4 h-4 mr-1 ${dailyValidating ? 'animate-spin' : ''}`} />
            {dailyValidating ? '刷新中' : '刷新'}
          </Button>
        </div>
      </div>

      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted">統計行業數</p>
            <p className="text-lg font-semibold text-slate-100">{summary.count}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted">全市場平均漲跌幅</p>
            <p className={`text-lg font-semibold ${summary.avgPct >= 0 ? 'text-red-400' : 'text-green-400'}`}>
              {summary.avgPct.toFixed(3)}%
            </p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted">領漲行業</p>
            <p className="text-sm font-semibold text-slate-100 truncate">{summary.top.industry}</p>
            <p className="text-xs text-red-400">{summary.top.avgPctChg?.toFixed(3) ?? '-'}%</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <p className="text-xs text-muted">全市場總成交</p>
            <p className="text-lg font-semibold text-slate-100">{(summary.totalAmount / 1e9).toFixed(2)} 億</p>
          </div>
        </div>
      )}

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

      {view === 'trend' && (
        <div className="flex flex-col md:flex-row flex-wrap gap-2 rounded-md border border-border bg-bg-panel p-3">
          <select
            value={selectedIndustry}
            onChange={(e) => setSelectedIndustry(e.target.value)}
            className="bg-bg-base text-sm text-slate-100 rounded border border-border px-3 py-2 outline-none min-w-[200px]"
          >
            <option value="">請選擇行業</option>
            {industries.map((ind) => (
              <option key={ind} value={ind}>
                {ind}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted">起始</span>
            <input
              type="date"
              value={rangeStart}
              onChange={(e) => setRangeStart(e.target.value)}
              className="bg-bg-base text-sm text-slate-100 rounded border border-border px-2 py-1 outline-none"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted">結束</span>
            <input
              type="date"
              value={rangeEnd}
              onChange={(e) => setRangeEnd(e.target.value)}
              className="bg-bg-base text-sm text-slate-100 rounded border border-border px-2 py-1 outline-none"
            />
          </div>
          <Button onClick={() => mutateTrend()} size="sm" variant="outline" disabled={trendValidating || !selectedIndustry}>
            {trendValidating ? (
              <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
            ) : (
              <TrendingUp className="w-4 h-4 mr-1" />
            )}
            載入走勢
          </Button>
        </div>
      )}

      <div className="w-full min-h-[300px]">
        {view === 'trend' ? renderTrend() : renderChart()}
      </div>

      {/* 行業新聞列表（僅在走勢視圖下顯示） */}
      {view === 'trend' && selectedIndustry && (
        <div className="rounded-lg border border-border bg-bg-panel p-4">
          <div className="flex items-center gap-2 mb-3">
            <Newspaper className="w-4 h-4 text-accent" />
            <h3 className="text-sm font-semibold text-slate-100">
              「{selectedIndustry}」相關新聞
            </h3>
            {newsLoading && <RefreshCw className="w-3 h-3 animate-spin text-muted" />}
            {newsError && <span className="text-xs text-red-400">（新聞載入失敗）</span>}
            {!newsLoading && !newsError && newsData && (
              <span className="text-xs text-muted">共 {newsData.news.length} 條</span>
            )}
          </div>
          {newsData && newsData.news.length > 0 ? (
            <ul className="space-y-2 max-h-60 overflow-auto">
              {newsData.news.map((n, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="text-xs text-muted flex-shrink-0 mt-0.5">{n.date || '-'}</span>
                  <a
                    href={n.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-slate-300 hover:text-accent truncate"
                    title={n.title}
                  >
                    {n.title}
                  </a>
                  <span className="text-xs text-muted flex-shrink-0">{n.source}</span>
                </li>
              ))}
            </ul>
          ) : (
            !newsLoading && <p className="text-sm text-muted">暫無相關新聞</p>
          )}
        </div>
      )}
    </div>
  );
}
