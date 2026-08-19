/**
 * @file ScreenerPage 選股器與回測頁 — 左右分欄佈局，
 * 左側為選股條件、回測配置和策略管理面板，右側為選股結果、候選詳情和回測結果。
 */
'use client';

import { useState, useCallback } from 'react';
import { ScreenerFilterPanel } from '@/components/screener/ScreenerFilterPanel';
import { ScreenerResultTable } from '@/components/screener/ScreenerResultTable';
import { CandidateDetail } from '@/components/screener/CandidateDetail';
import { BacktestConfigPanel } from '@/components/backtest/BacktestConfigPanel';
import { BacktestStatisticsPanel } from '@/components/backtest/BacktestStatisticsPanel';
import { BacktestCurveChart } from '@/components/chart/BacktestCurveChart';
import { RebalanceTable } from '@/components/backtest/RebalanceTable';
import { StrategyManager } from '@/components/backtest/StrategyManager';
import { StrategyComparePanel } from '@/components/backtest/StrategyComparePanel';
import { LogPanel } from '@/components/dashboard/LogPanel';
import { ErrorState } from '@/components/ui/ErrorState';
import { ProgressIndicator } from '@/components/ui/ProgressIndicator';
import { Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import type {
  ScreenerCriteriaDto,
  ScreenerResultDto,
  ScreenedStockDto,
  BacktestConfigDto,
  BacktestResultDto,
  SavedStrategyDetailDto,
} from '@/lib/api/types';

/** 今日日期（YYYY-MM-DD 格式） */
const today = new Date().toISOString().slice(0, 10);

/** 默認選股條件 */
const defaultCriteria: ScreenerCriteriaDto = {
  asOfDate: today,
  adjustflag: 3,
  excludeSt: true,
  maxResults: 100,
  sortBy: 'score',
};

/** 默認回測配置（今年至今，避免大範圍回測超時） */
const defaultBacktestConfig: BacktestConfigDto = {
  startDate: `${today.slice(0, 4)}-01-01`,
  endDate: today,
  rebalanceInterval: 5,
  holdingPeriod: 10,
  maxPositions: 5,
  initialCapital: 1_000_000,
  commissionBps: 3,
  stopLossPct: null,
  takeProfitPct: null,
};

/**
 * ScreenerPage 選股器與回測頁組件。
 * 管理選股條件、回測配置、結果狀態和策略對比，支持 CSV 導出。
 */
export default function ScreenerPage() {
  const [criteria, setCriteria] = useState<ScreenerCriteriaDto>(defaultCriteria);
  const [screenerResult, setScreenerResult] = useState<ScreenerResultDto | null>(null);
  const [selected, setSelected] = useState<ScreenedStockDto | null>(null);
  const [backtestConfig, setBacktestConfig] = useState<BacktestConfigDto>(defaultBacktestConfig);
  const [backtestResult, setBacktestResult] = useState<BacktestResultDto | null>(null);
  const [runningBacktest, setRunningBacktest] = useState(false);
  const [runningScreener, setRunningScreener] = useState(false);
  const [screenerError, setScreenerError] = useState<string | null>(null);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [compareStrategies, setCompareStrategies] = useState<SavedStrategyDetailDto[]>([]);
  const [autoSave, setAutoSave] = useState(true); // 回測自動保存開關（默認開啟）

  const runScreener = useCallback(async () => {
    setRunningScreener(true);
    setScreenerError(null);
    try {
      const result = await api.runScreener(criteria);
      setScreenerResult(result);
      setSelected(result.candidates[0] ?? null);
    } catch (e) {
      setScreenerError((e as Error).message);
    } finally {
      setRunningScreener(false);
    }
  }, [criteria]);

  const runBacktest = useCallback(async () => {
    setRunningBacktest(true);
    setBacktestError(null);
    try {
      // 自動保存開啟時調用 run-and-save 端點，結果自動寫入數據庫
      const result = autoSave
        ? await api.runBacktestAndSave({ criteria, config: backtestConfig })
        : await api.runBacktest({ criteria, config: backtestConfig });
      setBacktestResult(result);
    } catch (e) {
      setBacktestError((e as Error).message);
    } finally {
      setRunningBacktest(false);
    }
  }, [criteria, backtestConfig, autoSave]);

  // 載入歷史策略：更新選股條件、回測配置和可選的結果
  const loadStrategy = useCallback((
    loadedCriteria: ScreenerCriteriaDto,
    loadedConfig: BacktestConfigDto,
    loadedResult: BacktestResultDto | null,
  ) => {
    setCriteria(loadedCriteria);
    setBacktestConfig(loadedConfig);
    setBacktestResult(loadedResult);
  }, []);

  const exportCsv = () => {
    if (!screenerResult) return;
    const rows = screenerResult.candidates;
    if (rows.length === 0) return;
    const headers = ['code', 'tradeDate', 'score', 'closePrice', 'pctChange', 'turn', 'volumeRatio', 'return20', 'return60', 'return120', 'rsi14', 'macdCrossSignal', 'kdjCrossSignal', 'bollPosition'];
    const lines = [headers.join(',')];
    for (const r of rows) {
      lines.push(headers.map((h) => (r as unknown as Record<string, unknown>)[h] ?? '').join(','));
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `screener_${today}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* 進度指示器 */}
      <ProgressIndicator
        active={runningScreener}
        label="正在运行选股"
        stages={['正在读取行情数据...', '正在计算技术指标...', '正在筛选符合条件的股票...', '正在排序结果...']}
      />
      <ProgressIndicator
        active={runningBacktest}
        label="正在运行回测（可能需要 1-2 分钟，请耐心等待）"
        stages={['正在拉取回测区间数据...', '正在模拟调仓交易...', '正在计算净值曲线...', '正在生成统计指标...']}
      />

      {/* 左右分欄佈局：左側控制面板，右側結果 */}
      <div className="grid grid-cols-1 xl:grid-cols-[380px_1fr] gap-4 items-start">
        {/* 左側：固定控制面板 */}
        <div className="xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-auto space-y-4 pb-4">
          <ScreenerFilterPanel
            criteria={criteria}
            onChange={setCriteria}
            onRun={runScreener}
            onExport={exportCsv}
            running={runningScreener}
          />
          <BacktestConfigPanel
            config={backtestConfig}
            onChange={setBacktestConfig}
            onRun={runBacktest}
            loading={runningBacktest}
            autoSave={autoSave}
            onToggleAutoSave={setAutoSave}
          />
          <StrategyManager
            criteria={criteria}
            config={backtestConfig}
            result={backtestResult}
            onLoadStrategy={loadStrategy}
            onCompareStrategies={setCompareStrategies}
          />
        </div>

        {/* 右側：結果區 */}
        <div className="space-y-4 min-w-0">
          {/* 策略對比 */}
          {compareStrategies.length > 0 && (
            <StrategyComparePanel
              strategies={compareStrategies}
              onClose={() => setCompareStrategies([])}
            />
          )}

          {/* 選股結果 */}
          {screenerError && <ErrorState message={`选股失败: ${screenerError}`} onRetry={runScreener} />}

          {runningScreener && !screenerResult && (
            <div className="rounded-lg border border-border bg-bg-panel p-12 text-center">
              <Loader2 />
              <div className="text-muted text-sm mt-3">正在运行选股，请稍候...</div>
            </div>
          )}

          {screenerResult && (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 min-w-0">
                  <ScreenerResultTable
                    candidates={screenerResult.candidates}
                    onSelect={setSelected}
                    selected={selected?.code ?? null}
                  />
                </div>
                <CandidateDetail stock={selected} />
              </div>
              <LogPanel
                logs={screenerResult.summaryLines}
                statusText={`命中 ${screenerResult.matchedSymbols}/${screenerResult.scannedSymbols}`}
              />
            </>
          )}

          {/* 回測結果 */}
          {backtestError && <ErrorState message={`回测失败: ${backtestError}`} onRetry={runBacktest} />}

          {runningBacktest && !backtestResult && (
            <div className="rounded-lg border border-border bg-bg-panel p-12 text-center">
              <Loader2 />
              <div className="text-muted text-sm mt-3">正在运行回测，请稍候...</div>
            </div>
          )}

          {backtestResult && (
            <>
              <BacktestStatisticsPanel stats={backtestResult.statistics} />
              <BacktestCurveChart
                strategy={backtestResult.strategyCurve}
                benchmark={backtestResult.benchmarkCurve}
                excess={backtestResult.excessCurve}
              />
              <RebalanceTable rebalances={backtestResult.rebalances} />
              <LogPanel logs={backtestResult.logLines} />
            </>
          )}

          {/* 空狀態 */}
          {!screenerResult && !backtestResult && !runningScreener && !runningBacktest && (
            <div className="rounded-lg border border-border bg-bg-panel p-12 text-center">
              <div className="text-muted text-sm">
                设置左侧筛选条件后点击「运行选股」，配置回测参数后点击「运行回测」。
              </div>
              <div className="text-muted text-xs mt-2">
                运行历史策略可从左下角「策略管理」面板载入。
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
