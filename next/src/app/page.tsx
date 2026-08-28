/**
 * @file DashboardPage 總覽面板頁 — 應用首頁，
 * 展示儀表盤指標卡片、K線圖、波動列表和搜索結果表格，
 * 各資源通過獨立 SWR 調用漸進式加載，互不阻塞。
 */
'use client';

import { useState, useCallback, useMemo } from 'react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import { useInView } from '@/lib/hooks/useInView';
import { Toolbar, type ToolbarValues } from '@/components/dashboard/Toolbar';
import { MetricGrid } from '@/components/dashboard/MetricCard';
import { MoversList } from '@/components/dashboard/MoversList';
import { StockTable } from '@/components/dashboard/StockTable';
import { LogPanel } from '@/components/dashboard/LogPanel';
import { MarketSnapshotPanel } from '@/components/dashboard/MarketSnapshotPanel';
import { CandlestickChart } from '@/components/chart/CandlestickChart';
import {
  MetricGridSkeleton,
  TableSkeleton,
  ChartSkeleton,
  MoversSkeleton,
} from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { Button } from '@/components/ui/Button';
import { Loader2, ChevronDown } from 'lucide-react';
import type { StockDailyDto } from '@/lib/api/types';

/** 默認搜索條件 — 默認顯示上證指數 */
const DEFAULT_QUERY: ToolbarValues = {
  code: 'sh.000001',
  adjustflag: 3,
  startDate: '',
  endDate: '',
  limit: 50,
};

/**
 * DashboardPage 總覽面板頁組件 — 應用首頁。
 * 使用 4 個獨立 SWR 調用分別加載 Summary、Movers、Search 和 Chart 數據，
 * 支持分頁加載更多表格數據和點擊波動列表快速搜索。
 */
export default function DashboardPage() {
  const [query, setQuery] = useState<ToolbarValues>(DEFAULT_QUERY);
  const [tableRecords, setTableRecords] = useState<StockDailyDto[]>([]);
  const [tableHasMore, setTableHasMore] = useState(false);
  const [tableLoadingMore, setTableLoadingMore] = useState(false);
  const [tableOffset, setTableOffset] = useState(0);
  // 懶加載：各區域進入視口後才請求數據
  const [metricsRef, metricsInView] = useInView<HTMLDivElement>();
  const [chartMoversRef, chartMoversInView] = useInView<HTMLDivElement>();
  const [tableRef, tableInView] = useInView<HTMLDivElement>();

  // 構建搜索參數
  const searchParams = useMemo(() => {
    const params = new URLSearchParams();
    if (query.code) params.set('code', query.code);
    params.set('adjustflag', String(query.adjustflag));
    if (query.startDate) params.set('startDate', query.startDate);
    if (query.endDate) params.set('endDate', query.endDate);
    params.set('limit', String(query.limit));
    return params;
  }, [query]);

  // 獨立 SWR 調用 — 各資源獨立加載，互不阻塞
  // 1. Summary 指標（預計算數據，毫秒級返回）
  const { data: summary, error: summaryError, isLoading: summaryLoading, mutate: reloadSummary } = useSWR(
    metricsInView ? '/dashboard/summary' : null,
    () => api.summary(),
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  // 2. Movers 波動列表（預計算數據，快速返回）
  const { data: movers, error: moversError, isLoading: moversLoading, mutate: reloadMovers } = useSWR(
    chartMoversInView ? '/stock/movers?limit=8' : null,
    () => api.movers(8),
    { revalidateOnFocus: false, dedupingInterval: 30000 }
  );

  // 3. 搜索結果（默認加載上證指數數據）
  const searchKey = useMemo(() => `/stock/search?${searchParams.toString()}`, [searchParams]);
  const { data: searchResult, error: searchError, isLoading: searchLoading, mutate: reloadSearch } = useSWR(
    tableInView ? searchKey : null,
    () => api.search(searchParams),
    {
      revalidateOnFocus: false,
      onSuccess: (data) => {
        setTableRecords(data.items);
        setTableHasMore(data.hasMore);
        setTableOffset(0);
      },
    }
  );

  // 4. K線圖（依賴搜索結果的第一條記錄的 code）
  const chartCode = useMemo(() => {
    if (query.code && query.code.includes('.') && query.code.length >= 9) return query.code;
    return tableRecords.length > 0 ? tableRecords[0].code : '';
  }, [query.code, tableRecords]);

  const chartParams = useMemo(() => {
    const params = new URLSearchParams();
    if (chartCode) params.set('code', chartCode);
    params.set('adjustflag', String(query.adjustflag));
    if (query.startDate) params.set('startDate', query.startDate);
    if (query.endDate) params.set('endDate', query.endDate);
    params.set('limit', '120');
    return params;
  }, [chartCode, query]);

  const { data: chart, error: chartError, isLoading: chartLoading, mutate: reloadChart } = useSWR(
    chartCode ? `/chart/candlestick?${chartParams.toString()}` : null,
    () => api.candlestick(chartParams),
    { revalidateOnFocus: false, dedupingInterval: 30000 }
  );

  // 構建指標卡片數據
  const metrics = useMemo(() => {
    if (!summary) return null;
    const latestDateText = summary.latestTradeDate ?? '暂无数据';
    return [
      { title: '总记录数', value: summary.totalRecords.toLocaleString(), subtitle: 'stock_daily 表总行数' },
      { title: '股票数量', value: summary.totalSymbols.toLocaleString(), subtitle: '去重证券代码数量' },
      { title: '最新交易日', value: latestDateText, subtitle: '数据库内最新行情日期' },
      {
        title: '平均涨跌幅',
        value: summary.averagePctChange != null ? `${summary.averagePctChange.toFixed(2)}%` : '-',
        subtitle: '最新交易日，不复权口径',
      },
      {
        title: '最新成交额',
        value: summary.latestTurnover != null ? `${(summary.latestTurnover / 1e8).toFixed(2)} 亿` : '-',
        subtitle: '最新交易日，不复权口径',
      },
    ];
  }, [summary]);

  // 構建日誌
  const logs = useMemo(() => {
    const rangeText = (query.startDate && query.endDate)
      ? `${query.startDate} ~ ${query.endDate}`
      : '未设置日期区间';
    return [
      `搜索条件：code='${query.code || '全部'}'，adjustflag=${query.adjustflag}，日期 ${rangeText}，limit=${query.limit}`,
      `表格结果：${tableRecords.length} 条${tableHasMore ? '（可加载更多）' : ''}`,
      `K线图：${chartCode ? chartCode + '，已加载 ' + (chart?.records?.length ?? 0) + ' 根K线' : '无可用证券'}`,
    ];
  }, [query, tableRecords.length, tableHasMore, chartCode, chart]);

  const onSearch = useCallback((values: ToolbarValues) => {
    setQuery(values);
  }, []);

  const onReset = useCallback(() => {
    setQuery(DEFAULT_QUERY);
  }, []);

  // 點擊波動列表中的股票直接搜索
  const onSelectMover = useCallback((code: string) => {
    setQuery((prev) => ({ ...prev, code }));
  }, []);

  // 加載更多表格數據
  const loadMore = useCallback(async () => {
    if (!tableHasMore || tableLoadingMore) return;
    setTableLoadingMore(true);
    try {
      const params = new URLSearchParams(searchParams.toString());
      params.set('offset', String(tableOffset + query.limit));
      const result = await api.search(params);
      setTableRecords((prev) => [...prev, ...result.items]);
      setTableHasMore(result.hasMore);
      setTableOffset((prev) => prev + query.limit);
    } catch (e) {
      console.error('加载更多失败:', e);
    } finally {
      setTableLoadingMore(false);
    }
  }, [tableHasMore, tableLoadingMore, tableOffset, query.limit, searchParams]);

  return (
    <div className="space-y-6">
      <Toolbar
        defaults={DEFAULT_QUERY}
        externalValues={query}
        onSearch={onSearch}
        onReset={onReset}
        searching={searchLoading}
      />

      {/* 指標卡片 — 進入視口後懶加載 */}
      <div ref={metricsRef}>
        {(summaryLoading || !metrics) ? (
          <MetricGridSkeleton />
        ) : (
          <>
            {summaryLoading && <MetricGridSkeleton />}
            {summaryError && (
              <ErrorState message={`指标加载失败: ${summaryError.message}`} onRetry={reloadSummary} />
            )}
            {metrics && <MetricGrid metrics={metrics} />}
          </>
        )}
      </div>

      {/* K線圖 + 波動列表 — 進入視口後懶加載 */}
      <div ref={chartMoversRef} className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          {chartLoading && <ChartSkeleton />}
          {chartError && <ErrorState message={`K线图加载失败: ${chartError.message}`} onRetry={reloadChart} />}
          {chart && (
            <CandlestickChart
              initial={chart}
              adjustflag={query.adjustflag}
              startDate={query.startDate || null}
              endDate={query.endDate || null}
            />
          )}
          {!chartLoading && !chart && !chartError && (
            <div className="rounded-lg border border-border bg-bg-panel p-8 text-center text-muted">
              请输入股票代码搜索以加载K线图
            </div>
          )}
        </div>
        <div>
          {moversLoading && <MoversSkeleton />}
          {moversError && <ErrorState message={`波动列表加载失败: ${moversError.message}`} onRetry={reloadMovers} />}
          {movers && <MoversList movers={movers} onSelect={onSelectMover} />}
        </div>
      </div>

      {/* 搜索結果表格 — 進入視口後懶加載 */}
      <div ref={tableRef}>
      {searchLoading && tableRecords.length === 0 && <TableSkeleton />}
      {searchError && <ErrorState message={`搜索失败: ${searchError.message}`} onRetry={reloadSearch} />}
      {!searchLoading && !searchError && tableRecords.length === 0 && (
        <div className="rounded-lg border border-border bg-bg-panel p-8 text-center text-muted">
          暂无数据，请调整搜索条件后重试
        </div>
      )}
      {tableRecords.length > 0 && (
        <StockTable records={tableRecords} />
      )}

      {/* 加載更多按鈕 */}
      {tableHasMore && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={loadMore} disabled={tableLoadingMore}>
            {tableLoadingMore ? (
              <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> 加载中...</>
            ) : (
              <><ChevronDown className="w-4 h-4 mr-1" /> 加载更多</>
            )}
          </Button>
        </div>
      )}
      </div>

      {/* 行情預計算快照（預計算數據，毫秒級加載） */}
      <MarketSnapshotPanel />

      {/* 日誌面板 */}
      {logs.length > 0 && <LogPanel logs={logs} statusText="搜索结果已刷新" />}
    </div>
  );
}
