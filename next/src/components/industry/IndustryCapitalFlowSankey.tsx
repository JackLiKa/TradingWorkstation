'use client';

import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { IndustryDailyDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';

interface Props {
  rangeStart: string;
  rangeEnd: string;
}

/**
 * 行業間資金流向遷移圖（桑基圖）。
 *
 * 計算邏輯：
 * 1. 取區間內每個交易日的行業成交金額
 * 2. 計算每個行業的成交金額佔比（市場總成交的百分比）
 * 3. 比較相鄰交易日的佔比變化：
 *    - 佔比增加 = 資金流入
 *    - 佔比減少 = 資金流出
 * 4. 構建桑基圖：源節點為「流出行業」，目標節點為「流入行業」，流量為遷移金額
 */
export function IndustryCapitalFlowSankey({ rangeStart, rangeEnd }: Props) {
  const key = `/stock/industry-daily/all-range?start=${rangeStart}&end=${rangeEnd}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<IndustryDailyDto[]>(
    key,
    () => api.allIndustryDailyRange(rangeStart, rangeEnd),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );
  const canRender = useDelayedRender(isLoading);

  const { sankeyData, sankeyLinks, summary } = useMemo(() => {
    if (!data || data.length === 0) {
      return { sankeyData: [] as any[], sankeyLinks: [] as any[], summary: null };
    }

    // 1. 按日期分組
    const byDate = new Map<string, Map<string, number>>();
    for (const item of data) {
      if (item.totalAmount == null) continue;
      if (!byDate.has(item.tradeDate)) {
        byDate.set(item.tradeDate, new Map());
      }
      byDate.get(item.tradeDate)!.set(item.industry, item.totalAmount);
    }

    const sortedDates = Array.from(byDate.keys()).sort();
    if (sortedDates.length < 2) {
      return { sankeyData: [] as any[], sankeyLinks: [] as any[], summary: null };
    }

    // 2. 取首尾兩個交易日比較（也可取多日平均，這裡取首尾）
    const firstDate = sortedDates[0];
    const lastDate = sortedDates[sortedDates.length - 1];
    const firstData = byDate.get(firstDate)!;
    const lastData = byDate.get(lastDate)!;

    // 3. 計算各行業的成交金額佔比變化
    const firstTotal = Array.from(firstData.values()).reduce((s, v) => s + v, 0);
    const lastTotal = Array.from(lastData.values()).reduce((s, v) => s + v, 0);

    if (firstTotal === 0 || lastTotal === 0) {
      return { sankeyData: [] as any[], sankeyLinks: [] as any[], summary: null };
    }

    const allIndustries = new Set<string>([...firstData.keys(), ...lastData.keys()]);

    const flowList: { industry: string; firstShare: number; lastShare: number; change: number; firstAmount: number; lastAmount: number }[] = [];
    for (const ind of allIndustries) {
      const firstAmount = firstData.get(ind) ?? 0;
      const lastAmount = lastData.get(ind) ?? 0;
      const firstShare = firstAmount / firstTotal;
      const lastShare = lastAmount / lastTotal;
      const change = lastShare - firstShare;
      flowList.push({ industry: ind, firstShare, lastShare, change, firstAmount, lastAmount });
    }

    // 4. 取佔比變化最大的行業（流入 Top N + 流出 Top N）
    const TOP_N = 10;
    const inflowIndustries = flowList
      .filter((f) => f.change > 0)
      .sort((a, b) => b.change - a.change)
      .slice(0, TOP_N);
    const outflowIndustries = flowList
      .filter((f) => f.change < 0)
      .sort((a, b) => a.change - b.change)
      .slice(0, TOP_N);

    if (inflowIndustries.length === 0 || outflowIndustries.length === 0) {
      return { sankeyData: [] as any[], sankeyLinks: [] as any[], summary: null };
    }

    // 5. 計算總遷移量（流出總量 = 流入總量）
    const totalOutflow = outflowIndustries.reduce((s, f) => s + Math.abs(f.change), 0);
    const totalInflow = inflowIndustries.reduce((s, f) => s + f.change, 0);
    const totalMigration = Math.min(totalOutflow, totalInflow);

    if (totalMigration === 0) {
      return { sankeyData: [] as any[], sankeyLinks: [] as any[], summary: null };
    }

    // 6. 構建桑基圖節點
    // 左側：流出行業（加後綴 _out 避免與流入行業同名衝突）
    // 右側：流入行業（加後綴 _in）
    const nodes: any[] = [];
    for (const f of outflowIndustries) {
      const shortName = f.industry.replace(/[A-Z]\d+/, '').trim() || f.industry;
      nodes.push({
        name: `${shortName} ↓`,
        itemStyle: { color: '#22c55e' },
      });
    }
    for (const f of inflowIndustries) {
      const shortName = f.industry.replace(/[A-Z]\d+/, '').trim() || f.industry;
      nodes.push({
        name: `${shortName} ↑`,
        itemStyle: { color: '#ef4444' },
      });
    }

    // 7. 構建桑基圖連結
    // 按比例分配：每個流出行業的資金按比例流向每個流入行業
    const links: any[] = [];
    for (const out of outflowIndustries) {
      const outShortName = out.industry.replace(/[A-Z]\d+/, '').trim() || out.industry;
      const outFlowAmount = Math.abs(out.change) * firstTotal / 1e8; // 轉為億元
      for (const in_ of inflowIndustries) {
        const inShortName = in_.industry.replace(/[A-Z]\d+/, '').trim() || in_.industry;
        const inFlowAmount = in_.change * lastTotal / 1e8;
        // 按流入行業的佔比分配流出
        const flowValue = (inFlowAmount / totalInflow) * outFlowAmount;
        if (flowValue > 0.01) { // 過濾極小流量
          links.push({
            source: `${outShortName} ↓`,
            target: `${inShortName} ↑`,
            value: Number(flowValue.toFixed(2)),
          });
        }
      }
    }

    // 8. 統計摘要
    const totalMigrationYi = totalMigration * firstTotal / 1e8;
    const summary = {
      firstDate,
      lastDate,
      totalMigration: totalMigrationYi,
      inflowCount: inflowIndustries.length,
      outflowCount: outflowIndustries.length,
      topInflow: inflowIndustries.slice(0, 5).map((f) => ({
        industry: f.industry,
        change: f.change * 100,
        amount: f.change * lastTotal / 1e8,
      })),
      topOutflow: outflowIndustries.slice(0, 5).map((f) => ({
        industry: f.industry,
        change: f.change * 100,
        amount: Math.abs(f.change) * firstTotal / 1e8,
      })),
    };

    return { sankeyData: nodes, sankeyLinks: links, summary };
  }, [data]);

  const option = useMemo(() => {
    if (sankeyData.length === 0 || sankeyLinks.length === 0) return null;

    return {
      title: {
        text: `行業資金流向遷移圖（${summary?.firstDate} → ${summary?.lastDate}）`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'edge') {
            return `${params.data.source} → ${params.data.target}<br/>遷移資金: ${params.data.value} 億元`;
          }
          return params.data.name;
        },
      },
      series: [
        {
          type: 'sankey',
          data: sankeyData,
          links: sankeyLinks,
          emphasis: {
            focus: 'adjacency',
          },
          lineStyle: {
            color: 'gradient',
            curveness: 0.5,
            opacity: 0.4,
          },
          label: {
            color: '#e2e8f0',
            fontSize: 10,
          },
          itemStyle: {
            borderWidth: 0,
          },
          levels: [
            {
              depth: 0,
              itemStyle: { color: '#22c55e' },
              lineStyle: { color: 'source', opacity: 0.3 },
            },
            {
              depth: 1,
              itemStyle: { color: '#ef4444' },
              lineStyle: { color: 'target', opacity: 0.3 },
            },
          ],
          left: '5%',
          right: '5%',
          top: '15%',
          bottom: '10%',
          nodeWidth: 15,
          nodeGap: 8,
        },
      ],
    };
  }, [sankeyData, sankeyLinks, summary]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <RefreshButton
          onClick={() => mutate()}
          isLoading={isValidating}
          className="ml-auto"
        />
      </div>

      {/* 遷移統計摘要 */}
      {summary && (
        <div className="rounded-lg border border-border bg-bg-panel p-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
            <div className="text-center">
              <div className="text-muted">比較區間</div>
              <div className="font-medium text-fg">{summary.firstDate} → {summary.lastDate}</div>
            </div>
            <div className="text-center">
              <div className="text-muted">總遷移資金</div>
              <div className="font-medium text-amber-400">{summary.totalMigration.toFixed(2)} 億</div>
            </div>
            <div className="text-center">
              <div className="text-muted">流入行業數</div>
              <div className="font-medium text-red-400">{summary.inflowCount}</div>
            </div>
            <div className="text-center">
              <div className="text-muted">流行業數</div>
              <div className="font-medium text-green-400">{summary.outflowCount}</div>
            </div>
          </div>
        </div>
      )}

      {(isLoading || !canRender) && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && canRender && option && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[550px]">
          <ReactECharts option={option} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}
      {!isLoading && !error && !option && (
        <div className="rounded-lg border border-border bg-bg-panel p-8 text-center text-sm text-muted">
          數據不足或無明顯資金遷移，請擴大日期區間或確認數據已同步。
        </div>
      )}

      {/* 流入/流出排行 */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <h4 className="text-sm font-semibold text-red-400 mb-2">資金流入 Top 5</h4>
            <div className="space-y-1">
              {summary.topInflow.map((f, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate" title={f.industry}>{f.industry}</span>
                  <span className="text-red-400 ml-2 flex-shrink-0">
                    +{f.change.toFixed(2)}% · {f.amount.toFixed(2)}億
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <h4 className="text-sm font-semibold text-green-400 mb-2">資金流出 Top 5</h4>
            <div className="space-y-1">
              {summary.topOutflow.map((f, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate" title={f.industry}>{f.industry}</span>
                  <span className="text-green-400 ml-2 flex-shrink-0">
                    {f.change.toFixed(2)}% · {f.amount.toFixed(2)}億
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <p className="text-xs text-muted">
        桑基圖展示首尾交易日各行業成交金額佔比的遷移。綠色節點為資金流出行業（佔比下降），紅色節點為資金流入行業（佔比上升）。
      </p>
    </div>
  );
}
