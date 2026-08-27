/**
 * @file AgentIterationCard 組件 — 展示單輪 AI 優化迭代的可摺疊卡片，
 * 包含回測統計、6 個 AI 階段輸出、選股條件摘要和評委評分結果。
 */
'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Award, AlertCircle, Bot, TrendingUp, TrendingDown, Brain, Lightbulb, PenLine, BarChart3, Gavel, CheckCircle2, XCircle, Clock, Newspaper, Filter, Layers } from 'lucide-react';
import type { AgentIteration, StageResult } from '@/lib/api/types';

/** AgentIterationCard 組件屬性 */
interface Props {
  /** 單輪迭代的完整數據 */
  iteration: AgentIteration;
  /** 是否為最佳迭代（用於高亮顯示） */
  isBest: boolean;
  /** 是否默認展開 */
  defaultExpanded?: boolean;
}

/**
 * AgentIterationCard 組件 — 可摺疊的迭代記錄卡片。
 * 摺疊狀態顯示輪次、評分和關鍵統計；展開後顯示回測統計、AI 輸出、選股條件和評委結果。
 * @param iteration 迭代數據
 * @param isBest 是否為最佳迭代
 * @param defaultExpanded 是否默認展開，默認 false
 */
export function AgentIterationCard({ iteration, isBest, defaultExpanded = false }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const stats = iteration.backtest_statistics;
  const totalReturn = stats?.totalReturn ?? 0;
  const maxDrawdown = stats?.maxDrawdown ?? 0;
  const sharpe = stats?.sharpe ?? 0;
  const excessReturn = stats?.excessReturn ?? 0;

  const hasError = !!iteration.error;

  return (
    <div
      className={`rounded-lg border p-3 transition-colors ${
        hasError
          ? 'border-red-500/30 bg-red-500/5'
          : isBest
          ? 'border-amber-500/40 bg-amber-500/5'
          : 'border-border bg-bg-base/50'
      }`}
    >
      {/* 摺疊頭部 */}
      <div className="flex items-center justify-between gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {isBest && !hasError && <Award className="w-4 h-4 text-amber-400 flex-shrink-0" />}
          {hasError && <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />}
          <span className="font-medium text-sm flex-shrink-0">第 {iteration.iteration} 輪</span>
          {!hasError && (
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              iteration.composite_score >= 60 ? 'bg-green-500/15 text-green-400' :
              iteration.composite_score >= 40 ? 'bg-amber-500/15 text-amber-400' :
              'bg-red-500/15 text-red-400'
            }`}>
              評分 {iteration.composite_score.toFixed(1)}
            </span>
          )}
          {hasError && <span className="text-xs text-red-400">錯誤</span>}
          {!hasError && iteration.favorable_industries && iteration.favorable_industries.length > 0 && (
            <span className="text-xs text-teal-400 hidden sm:inline">
              {iteration.favorable_industries.length} 行業 · {iteration.filtered_codes?.length ?? 0} 股票
            </span>
          )}
          {!hasError && Array.isArray(iteration.criteria?.industries) && (iteration.criteria!.industries as string[]).length > 0 && (
            <span className="text-xs text-amber-400 hidden md:inline flex items-center gap-0.5">
              <Layers className="w-3 h-3" />
              聚焦 {(iteration.criteria!.industries as string[]).length} 行業
            </span>
          )}
          <span className="text-xs text-muted truncate">{new Date(iteration.timestamp).toLocaleTimeString('zh-TW')}</span>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {!hasError && (
            <div className="flex items-center gap-3 text-xs">
              <span className={totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}>
                {totalReturn >= 0 ? <TrendingUp className="w-3 h-3 inline mr-0.5" /> : <TrendingDown className="w-3 h-3 inline mr-0.5" />}
                {totalReturn.toFixed(2)}%
              </span>
              <span className="text-muted">回撤 {maxDrawdown.toFixed(2)}%</span>
              <span className="text-muted">夏普 {sharpe.toFixed(2)}</span>
            </div>
          )}
          {expanded ? <ChevronUp className="w-4 h-4 text-muted" /> : <ChevronDown className="w-4 h-4 text-muted" />}
        </div>
      </div>

      {/* 展開內容 */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-border space-y-3">
          {hasError ? (
            <div className="text-sm text-red-400 bg-red-500/10 rounded p-2">
              {iteration.error}
            </div>
          ) : (
            <>
              {/* 策略摘要 — 一目了然看到本輪優化的策略和結果 */}
              <StrategySummary
                iteration={iteration}
                totalReturn={totalReturn}
                maxDrawdown={maxDrawdown}
                sharpe={sharpe}
                excessReturn={excessReturn}
              />

              {/* AI 0: 行情新聞 */}
              {iteration.market_news && (
                <AICard
                  icon={Newspaper}
                  label="AI 0 · 行情新聞"
                  content={iteration.market_news}
                  color="text-cyan-400"
                  bgColor="bg-cyan-500/5 border-cyan-500/10"
                />
              )}

              {/* AI 0.5: 行業篩選 */}
              {iteration.favorable_industries && iteration.favorable_industries.length > 0 && (
                <IndustryAnalysisCard
                  industries={iteration.favorable_industries}
                  filteredCodes={iteration.filtered_codes ?? []}
                />
              )}

              {/* 回測統計卡片 */}
              <div>
                <SectionTitle icon={BarChart3} label="回測統計" />
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                  <StatItem label="總收益" value={`${totalReturn.toFixed(2)}%`} positive={totalReturn >= 0} />
                  <StatItem label="年化收益" value={`${(stats?.annualReturn ?? 0).toFixed(2)}%`} positive={(stats?.annualReturn ?? 0) >= 0} />
                  <StatItem label="超額收益" value={`${excessReturn.toFixed(2)}%`} positive={excessReturn >= 0} />
                  <StatItem label="最大回撤" value={`${maxDrawdown.toFixed(2)}%`} negative />
                  <StatItem label="夏普比率" value={sharpe.toFixed(2)} />
                  <StatItem label="調倉次數" value={String(stats?.rebalanceCount ?? 0)} />
                  <StatItem label="交易筆數" value={String(stats?.totalTrades ?? 0)} />
                  <StatItem label="綜合評分" value={iteration.composite_score.toFixed(1)} highlight />
                </div>
              </div>

              {/* AI 1: 行情分析 */}
              {iteration.market_analysis && (
                <AICard
                  icon={Brain}
                  label="AI 1 · 行情分析"
                  content={iteration.market_analysis}
                  color="text-blue-400"
                  bgColor="bg-blue-500/5 border-blue-500/10"
                />
              )}

              {/* AI 2: 策略生成 */}
              {iteration.strategy_generation && (
                <AICard
                  icon={Lightbulb}
                  label="AI 2 · 策略生成"
                  content={iteration.strategy_generation}
                  color="text-purple-400"
                  bgColor="bg-purple-500/5 border-purple-500/10"
                />
              )}

              {/* AI 3: 回測反思 */}
              {iteration.backtest_reflection && (
                <AICard
                  icon={Bot}
                  label="AI 3 · 回測反思"
                  content={iteration.backtest_reflection}
                  color="text-amber-400"
                  bgColor="bg-amber-500/5 border-amber-500/10"
                />
              )}

              {/* AI 4: 提示詞生成 */}
              {iteration.next_prompt && (
                <AICard
                  icon={PenLine}
                  label="AI 4 · 下一輪指引"
                  content={iteration.next_prompt}
                  color="text-green-400"
                  bgColor="bg-green-500/5 border-green-500/10"
                />
              )}

              {/* 選股條件摘要（非 JSON，顯示激活的條件） */}
              {iteration.criteria && Object.keys(iteration.criteria).length > 0 && (
                <div>
                  <SectionTitle icon={BarChart3} label="選股條件" />
                  <CriteriaCard criteria={iteration.criteria} />
                </div>
              )}

              {/* 評委結果 */}
              {iteration.stage_results && iteration.stage_results.length > 0 && (
                <div>
                  <SectionTitle icon={Gavel} label="評委評分" />
                  <div className="space-y-1.5">
                    {iteration.stage_results.map((sr) => (
                      <JudgeResultCard key={sr.stage_name} result={sr} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** 區塊標題組件（圖標 + 標籤文字） */
function SectionTitle({ icon: Icon, label }: { icon: typeof Bot; label: string }) {
  return (
    <div className="text-xs font-medium text-muted mb-1.5 flex items-center gap-1">
      <Icon className="w-3 h-3" />
      {label}
    </div>
  );
}

/** AI 輸出卡片組件（圖標 + 標籤 + 內容文本） */
function AICard({ icon: Icon, label, content, color, bgColor }: {
  icon: typeof Bot;
  label: string;
  content: string;
  color: string;
  bgColor: string;
}) {
  return (
    <div className={`rounded border p-2.5 ${bgColor}`}>
      <div className={`text-xs font-medium mb-1 flex items-center gap-1 ${color}`}>
        <Icon className="w-3 h-3" />
        {label}
      </div>
      <div className="text-sm text-slate-300 whitespace-pre-wrap">{content}</div>
    </div>
  );
}

/** 選股條件摘要卡片 — 只顯示激活的條件，將字段名映射為中文標籤 */
function CriteriaCard({ criteria }: { criteria: Record<string, unknown> }) {
  // 只顯示激活的條件（非 null/false/"any"/0）
  const activeFilters = Object.entries(criteria).filter(
    ([, v]) => v !== null && v !== false && v !== "any" && v !== 0 && v !== "" && v !== undefined
  );

  if (activeFilters.length === 0) {
    return <div className="text-sm text-muted">無激活條件（默認選股）</div>;
  }

  const labelMap: Record<string, string> = {
    asOfDate: "基準日期",
    adjustflag: "復權類型",
    excludeSt: "排除ST",
    maxResults: "最大結果數",
    sortBy: "排序方式",
    minClose: "最低收盤價",
    maxClose: "最高收盤價",
    minPctChange: "最低漲跌幅",
    maxPctChange: "最高漲跌幅",
    minTurn: "最低換手率",
    maxTurn: "最高換手率",
    minAmplitude: "最低振幅",
    maxAmplitude: "最高振幅",
    minVolume: "最低成交量",
    minAmount: "最低成交額",
    minVolumeRatio: "最低量比",
    maxVolumeRatio: "最高量比",
    minReturn20: "最低20日收益",
    maxReturn20: "最高20日收益",
    minReturn60: "最低60日收益",
    maxReturn60: "最高60日收益",
    minReturn120: "最低120日收益",
    maxReturn120: "最高120日收益",
    minRsi14: "最低RSI14",
    maxRsi14: "最高RSI14",
    minKValue: "最低K值",
    maxKValue: "最高K值",
    minJValue: "最低J值",
    maxJValue: "最高J值",
    minMacdHist: "最低MACD柱",
    maxMacdHist: "最高MACD柱",
    macdCrossSignal: "MACD交叉",
    macdCrossWithinDays: "MACD交叉天數",
    kdjCrossSignal: "KDJ交叉",
    kdjCrossWithinDays: "KDJ交叉天數",
    bollPosition: "布林帶位置",
    priceAboveMa5: "價格>MA5",
    priceAboveMa20: "價格>MA20",
    priceAboveMa60: "價格>MA60",
    ma5AboveMa20: "MA5>MA20",
    ma20AboveMa60: "MA20>MA60",
    industries: "行業聚焦",
  };

  const valueFormat: Record<string, (v: unknown) => string> = {
    adjustflag: (v) => ({ 1: "後復權", 2: "前復權", 3: "不復權" }[v as number] ?? String(v)),
    macdCrossSignal: (v) => ({ golden_cross: "金叉", death_cross: "死叉", none: "無", any: "任意" }[v as string] ?? String(v)),
    kdjCrossSignal: (v) => ({ golden_cross: "金叉", death_cross: "死叉", none: "無", any: "任意" }[v as string] ?? String(v)),
    bollPosition: (v) => ({ upper: "上軌", middle: "中軌", lower: "下軌", any: "任意" }[v as string] ?? String(v)),
    industries: (v) => Array.isArray(v) ? v.join(', ') : String(v),
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {activeFilters.map(([key, value]) => {
        const label = labelMap[key] ?? key;
        const formatted = valueFormat[key] ? valueFormat[key](value) : String(value);
        return (
          <span key={key} className="text-xs px-2 py-1 rounded bg-bg-base/60 border border-border text-slate-300">
            <span className="text-muted">{label}: </span>
            <span className="font-medium">{formatted}</span>
          </span>
        );
      })}
    </div>
  );
}

/** 統計數據項組件（標籤 + 值，支持漲跌顏色和高亮） */
function StatItem({ label, value, positive, negative, highlight }: {
  label: string;
  value: string;
  positive?: boolean;
  negative?: boolean;
  highlight?: boolean;
}) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-muted">{label}</span>
      <span className={`font-medium ${
        highlight ? 'text-amber-400' :
        positive ? 'text-green-400' :
        negative ? 'text-red-400' :
        'text-fg'
      }`}>
        {value}
      </span>
    </div>
  );
}

const STAGE_LABELS: Record<string, string> = {
  market_news: '行情新聞',
  industry_analysis: '行業分析',
  market_analysis: '行情分析',
  strategy_generation: '策略生成',
  backtest_reflection: '回測反思',
  prompt_generation: '提示詞生成',
};

/** 策略摘要 — 本輪優化的策略核心信息一覽 */
function StrategySummary({ iteration, totalReturn, maxDrawdown, sharpe, excessReturn }: {
  iteration: AgentIteration;
  totalReturn: number;
  maxDrawdown: number;
  sharpe: number;
  excessReturn: number;
}) {
  const score = iteration.composite_score;
  const scoreColor = score >= 60 ? 'text-green-400' : score >= 40 ? 'text-amber-400' : 'text-red-400';
  const scoreBg = score >= 60 ? 'bg-green-500/10 border-green-500/20' : score >= 40 ? 'bg-amber-500/10 border-amber-500/20' : 'bg-red-500/10 border-red-500/20';

  return (
    <div className={`rounded-lg border p-3 ${scoreBg}`}>
      <div className="flex items-center gap-2 mb-2">
        <Award className="w-4 h-4 text-amber-400" />
        <span className="text-sm font-medium">策略摘要</span>
        <span className={`text-lg font-bold ml-auto ${scoreColor}`}>{score.toFixed(1)} 分</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
        <div className="flex flex-col">
          <span className="text-muted">總收益率</span>
          <span className={`font-medium ${totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-muted">超額收益</span>
          <span className={`font-medium ${excessReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {excessReturn >= 0 ? '+' : ''}{excessReturn.toFixed(2)}%
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-muted">最大回撤</span>
          <span className="font-medium text-red-400">{maxDrawdown.toFixed(2)}%</span>
        </div>
        <div className="flex flex-col">
          <span className="text-muted">夏普比率</span>
          <span className="font-medium text-fg">{sharpe.toFixed(3)}</span>
        </div>
      </div>
      {/* 選股條件摘要 */}
      {Boolean(iteration.criteria && Object.keys(iteration.criteria).length > 0) && (
        <div className="mt-2 pt-2 border-t border-border/50">
          <CriteriaCard criteria={iteration.criteria} />
        </div>
      )}
      {/* 行業聚焦摘要 — 突出顯示 AI 選擇的強勢行業 */}
      {Boolean(Array.isArray(iteration.criteria?.industries) && (iteration.criteria!.industries as string[]).length > 0) && (
        <div className="mt-2 pt-2 border-t border-border/50">
          <div className="flex items-center gap-1 mb-1">
            <Layers className="w-3 h-3 text-teal-400" />
            <span className="text-xs text-teal-400 font-medium">行業聚焦（策略僅在這些行業內選股）</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {(iteration.criteria!.industries as string[]).map((ind) => (
              <span key={ind} className="text-xs px-1.5 py-0.5 rounded bg-teal-500/15 text-teal-300 border border-teal-500/25">
                {ind}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** 行業分析卡片 — 顯示利好行業和篩選出的股票代碼 */
function IndustryAnalysisCard({ industries, filteredCodes }: {
  industries: string[];
  filteredCodes: string[];
}) {
  return (
    <div className="rounded border p-2.5 bg-teal-500/5 border-teal-500/10">
      <div className="text-xs font-medium mb-1.5 flex items-center gap-1 text-teal-400">
        <Filter className="w-3 h-3" />
        AI 0.5 · 行業篩選
      </div>
      {/* 利好行業 */}
      <div className="mb-2">
        <span className="text-xs text-muted">利好行業 ({industries.length})：</span>
        <div className="flex flex-wrap gap-1 mt-1">
          {industries.map((ind) => (
            <span key={ind} className="text-xs px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-300 border border-teal-500/20">
              {ind}
            </span>
          ))}
        </div>
      </div>
      {/* 篩選股票 */}
      {filteredCodes.length > 0 && (
        <div>
          <span className="text-xs text-muted">篩選股票 ({filteredCodes.length} 隻)：</span>
          <div className="flex flex-wrap gap-1 mt-1 max-h-20 overflow-y-auto">
            {filteredCodes.slice(0, 30).map((code) => (
              <span key={code} className="text-xs px-1.5 py-0.5 rounded bg-bg-base/60 border border-border text-slate-300 font-mono">
                {code}
              </span>
            ))}
            {filteredCodes.length > 30 && (
              <span className="text-xs text-muted self-center">...還有 {filteredCodes.length - 30} 隻</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** 評委評分結果卡片 — 顯示階段名稱、評分、通過/失敗狀態、重試次數和耗時 */
function JudgeResultCard({ result }: { result: StageResult }) {
  const label = STAGE_LABELS[result.stage_name] ?? result.stage_name;
  const passed = result.judge_passed;
  const hasError = !!result.error;

  return (
    <div className={`flex items-center gap-2 text-xs rounded border px-2 py-1.5 ${
      hasError
        ? 'border-red-500/20 bg-red-500/5'
        : passed
        ? 'border-green-500/20 bg-green-500/5'
        : 'border-orange-500/20 bg-orange-500/5'
    }`}>
      {hasError ? (
        <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
      ) : passed ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />
      ) : (
        <AlertCircle className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />
      )}

      <span className="font-medium text-slate-300 flex-shrink-0">{label}</span>

      <span className={`font-bold ${
        result.judge_score >= 80 ? 'text-green-400' :
        result.judge_score >= 60 ? 'text-amber-400' :
        'text-red-400'
      }`}>
        {result.judge_score.toFixed(0)}分
      </span>

      {result.attempts > 1 && (
        <span className="text-orange-400 flex items-center gap-0.5">
          <Clock className="w-3 h-3" />
          重試{result.attempts}次
        </span>
      )}

      <span className="text-muted ml-auto flex items-center gap-0.5">
        <Clock className="w-3 h-3" />
        {result.duration_ms > 1000 ? `${(result.duration_ms / 1000).toFixed(1)}s` : `${result.duration_ms}ms`}
      </span>

      {result.judge_feedback && (
        <span className="text-muted truncate max-w-[200px]" title={result.judge_feedback}>
          {result.judge_feedback}
        </span>
      )}
    </div>
  );
}
