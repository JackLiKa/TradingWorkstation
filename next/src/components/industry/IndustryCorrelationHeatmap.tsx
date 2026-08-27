'use client';

import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { IndustryDailyDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';
import { AnalysisTutorial } from '@/components/industry/AnalysisTutorial';

const TOP_N_OPTIONS = [10, 15, 20, 30];

interface Props {
  rangeStart: string;
  rangeEnd: string;
}

export function IndustryCorrelationHeatmap({ rangeStart, rangeEnd }: Props) {
  const [topN, setTopN] = useState(15);

  const key = `/stock/industry-daily/all-range?start=${rangeStart}&end=${rangeEnd}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<IndustryDailyDto[]>(
    key,
    () => api.allIndustryDailyRange(rangeStart, rangeEnd),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );
  const canRender = useDelayedRender(isLoading);

  // 計算行業相關性矩陣
  const { matrix, industries, stats } = useMemo(() => {
    if (!data || data.length === 0) {
      return { matrix: [] as number[][], industries: [] as string[], stats: null };
    }

    // 1. 按行業分組，構建每個行業的時間序列
    const industryMap = new Map<string, Map<string, number>>();
    for (const item of data) {
      if (item.avgPctChg == null) continue;
      if (!industryMap.has(item.industry)) {
        industryMap.set(item.industry, new Map());
      }
      industryMap.get(item.industry)!.set(item.tradeDate, item.avgPctChg);
    }

    // 2. 計算每個行業的波動率（標準差），取波動最大的 topN 行業（更有分析價值）
    const volatilityList = Array.from(industryMap.entries()).map(([ind, series]) => {
      const values = Array.from(series.values());
      const mean = values.reduce((s, v) => s + v, 0) / values.length;
      const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length;
      return { industry: ind, volatility: Math.sqrt(variance), series };
    });
    volatilityList.sort((a, b) => b.volatility - a.volatility);
    const selected = volatilityList.slice(0, topN);

    // 3. 對齊日期（取所有選中行業的交集日期）
    const allDates = new Set<string>();
    selected.forEach((s) => {
      Array.from(s.series.keys()).forEach((d) => allDates.add(d));
    });
    const sortedDates = Array.from(allDates).sort();

    // 4. 構建矩陣數據（每行一個行業的漲跌幅序列）
    const seriesData = selected.map((s) =>
      sortedDates.map((d) => s.series.get(d) ?? 0)
    );

    // 5. 計算 Pearson 相關係數矩陣
    const n = selected.length;
    const corrMatrix: number[][] = Array.from({ length: n }, () => new Array(n).fill(0));

    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (i === j) {
          corrMatrix[i][j] = 1;
        } else if (j > i) {
          const corr = pearsonCorrelation(seriesData[i], seriesData[j]);
          corrMatrix[i][j] = corr;
          corrMatrix[j][i] = corr;
        }
      }
    }

    // 6. 統計信息
    const correlations: number[] = [];
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        correlations.push(corrMatrix[i][j]);
      }
    }
    const avgCorr = correlations.length > 0
      ? correlations.reduce((s, v) => s + v, 0) / correlations.length
      : 0;
    const maxCorr = correlations.length > 0 ? Math.max(...correlations) : 0;
    const minCorr = correlations.length > 0 ? Math.min(...correlations) : 0;
    const highCorrPairs: { i: number; j: number; corr: number }[] = [];
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        if (corrMatrix[i][j] >= 0.7) {
          highCorrPairs.push({ i, j, corr: corrMatrix[i][j] });
        }
      }
    }
    highCorrPairs.sort((a, b) => b.corr - a.corr);

    return {
      matrix: corrMatrix,
      industries: selected.map((s) => s.industry),
      stats: {
        avgCorr,
        maxCorr,
        minCorr,
        highCorrPairs: highCorrPairs.slice(0, 5).map((p) => ({
          a: selected[p.i].industry,
          b: selected[p.j].industry,
          corr: p.corr,
        })),
        dateCount: sortedDates.length,
      },
    };
  }, [data, topN]);

  const option = useMemo(() => {
    if (matrix.length === 0 || industries.length === 0) return null;

    // 構建 ECharts 熱力圖數據
    const heatmapData: [number, number, number][] = [];
    for (let i = 0; i < industries.length; i++) {
      for (let j = 0; j < industries.length; j++) {
        heatmapData.push([j, i, Number(matrix[i][j].toFixed(3))]);
      }
    }

    // 簡化行業名稱顯示（去除代碼前綴）
    const shortNames = industries.map((name) => {
      const match = name.match(/[A-Z]\d+(.*)/);
      return match ? match[1] : name;
    });

    return {
      title: {
        text: `行業相關性矩陣（Top ${industries.length}，${rangeStart} ~ ${rangeEnd}）`,
        left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 14 },
      },
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const [x, y, value] = params.value;
          const indX = industries[x];
          const indY = industries[y];
          return `${indY}<br/>×<br/>${indX}<br/>相關係數: <b>${value.toFixed(3)}</b>`;
        },
      },
      grid: {
        left: '15%',
        right: '5%',
        bottom: '20%',
        top: '15%',
      },
      xAxis: {
        type: 'category',
        data: shortNames,
        splitArea: { show: true },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          rotate: 45,
          interval: 0,
        },
      },
      yAxis: {
        type: 'category',
        data: shortNames,
        splitArea: { show: true },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
        },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '2%',
        textStyle: { color: '#94a3b8' },
        inRange: {
          color: ['#22c55e', '#fbbf24', '#ef4444'], // 綠(負相關) → 黃(無相關) → 紅(正相關)
        },
      },
      series: [
        {
          name: '相關係數',
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: industries.length <= 15,
            color: '#fff',
            fontSize: 9,
            formatter: (p: any) => p.value[2].toFixed(2),
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    };
  }, [matrix, industries, rangeStart, rangeEnd]);

  return (
    <div className="space-y-3">
      <AnalysisTutorial tutorialKey="correlation" />
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">顯示行業數：</span>
        {TOP_N_OPTIONS.map((n) => (
          <button
            key={n}
            onClick={() => setTopN(n)}
            className={`px-2 py-1 rounded text-xs transition-colors ${
              topN === n
                ? 'bg-accent/10 text-accent'
                : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
            }`}
          >
            Top {n}
          </button>
        ))}
        <RefreshButton
          onClick={() => mutate()}
          isLoading={isValidating}
          className="ml-auto"
        />
      </div>

      {/* 統計摘要 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <div className="rounded border border-border bg-bg-panel p-2">
            <span className="text-muted">平均相關係數</span>
            <div className={`font-medium ${stats.avgCorr >= 0.5 ? 'text-red-400' : stats.avgCorr >= 0.3 ? 'text-amber-400' : 'text-green-400'}`}>
              {stats.avgCorr.toFixed(3)}
            </div>
          </div>
          <div className="rounded border border-border bg-bg-panel p-2">
            <span className="text-muted">最高相關係數</span>
            <div className="font-medium text-red-400">{stats.maxCorr.toFixed(3)}</div>
          </div>
          <div className="rounded border border-border bg-bg-panel p-2">
            <span className="text-muted">最低相關係數</span>
            <div className="font-medium text-green-400">{stats.minCorr.toFixed(3)}</div>
          </div>
          <div className="rounded border border-border bg-bg-panel p-2">
            <span className="text-muted">數據天數</span>
            <div className="font-medium text-fg">{stats.dateCount} 日</div>
          </div>
        </div>
      )}

      {(isLoading || !canRender) && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}
      {!isLoading && !error && canRender && option && (
        <div className="rounded-lg border border-border bg-bg-panel p-4 h-[600px]">
          <ReactECharts option={option} notMerge style={{ width: '100%', height: '100%' }} />
        </div>
      )}

      {/* 高相關行業對 */}
      {stats && stats.highCorrPairs.length > 0 && (
        <div className="rounded-lg border border-border bg-bg-panel p-3">
          <h4 className="text-sm font-semibold text-red-400 mb-2">高相關行業對（≥0.7，Top 5）</h4>
          <div className="space-y-1">
            {stats.highCorrPairs.map((pair, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="text-slate-300">
                  <span className="text-red-300">{pair.a}</span>
                  <span className="text-muted mx-1">×</span>
                  <span className="text-red-300">{pair.b}</span>
                </span>
                <span className="text-red-400 font-medium">{pair.corr.toFixed(3)}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted mt-2">
            高相關行業對走勢趨同，分散配置時應避免同時持有；低相關或負相關行業對更適合組合分散。
          </p>
        </div>
      )}
    </div>
  );
}

/** 計算 Pearson 相關係數 */
function pearsonCorrelation(x: number[], y: number[]): number {
  const n = Math.min(x.length, y.length);
  if (n < 2) return 0;

  const sumX = x.slice(0, n).reduce((s, v) => s + v, 0);
  const sumY = y.slice(0, n).reduce((s, v) => s + v, 0);
  const meanX = sumX / n;
  const meanY = sumY / n;

  let numerator = 0;
  let sumSqX = 0;
  let sumSqY = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - meanX;
    const dy = y[i] - meanY;
    numerator += dx * dy;
    sumSqX += dx * dx;
    sumSqY += dy * dy;
  }

  const denominator = Math.sqrt(sumSqX * sumSqY);
  if (denominator === 0) return 0;
  return numerator / denominator;
}
