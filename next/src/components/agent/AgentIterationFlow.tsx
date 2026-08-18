/**
 * @file AgentIterationFlow 組件 — 迭代階段流程指示器，
 * 在 Agent 運行時以水平進度條形式展示 7 個 AI 階段的執行進度。
 */
'use client';

import { Loader2, Brain, Lightbulb, FlaskConical, Bot, PenLine, CheckCircle2, XCircle, AlertCircle, Gavel, Newspaper, Filter } from 'lucide-react';
import type { AgentState } from '@/lib/api/types';

interface Props {
  state: AgentState | null;
}

/** 從 status_message 解析當前迭代階段 */
function parseStage(message: string): 'idle' | 'news' | 'industry' | 'market' | 'strategy' | 'backtesting' | 'reflection' | 'prompt' | 'waiting' | 'done' | 'error' {
  if (!message || message === 'idle') return 'idle';
  if (message.includes('行情新聞') || message.includes('AI 0 ')) return 'news';
  if (message.includes('行業') || message.includes('AI 0.5')) return 'industry';
  if (message.includes('行情分析') || message.includes('AI 1')) return 'market';
  if (message.includes('策略生成') || message.includes('AI 2')) return 'strategy';
  if (message.includes('回測中') || message.includes('運行回測')) return 'backtesting';
  if (message.includes('回測反思') || message.includes('AI 3')) return 'reflection';
  if (message.includes('提示詞') || message.includes('AI 4')) return 'prompt';
  if (message.includes('完成') || message.includes('準備下一輪')) return 'waiting';
  if (message.includes('停止') || message.includes('已停止')) return 'done';
  if (message.includes('錯誤') || message.includes('異常')) return 'error';
  return 'news';
}

const STAGES = [
  { key: 'news', label: '行情新聞', icon: Newspaper, color: 'text-cyan-400' },
  { key: 'industry', label: '行業篩選', icon: Filter, color: 'text-teal-400' },
  { key: 'market', label: '行情分析', icon: Brain, color: 'text-blue-400' },
  { key: 'strategy', label: '策略生成', icon: Lightbulb, color: 'text-purple-400' },
  { key: 'backtesting', label: '回測運行', icon: FlaskConical, color: 'text-cyan-400' },
  { key: 'reflection', label: '回測反思', icon: Bot, color: 'text-amber-400' },
  { key: 'prompt', label: '提示詞生成', icon: PenLine, color: 'text-green-400' },
] as const;

const STAGE_DESCRIPTIONS: Record<string, string> = {
  news: 'AI 0 正在抓取實時金融數據並分析行業情緒...',
  industry: 'AI 0.5 正在根據行情新聞篩選利好行業股票...',
  market: 'AI 1 正在分析市場環境和趨勢...',
  strategy: 'AI 2 正在根據市場分析生成選股條件...',
  backtesting: '正在用生成的選股條件運行回測...',
  reflection: 'AI 3 正在分析回測結果，反思策略表現...',
  prompt: 'AI 4 正在為下一輪生成指引提示詞...',
  waiting: '本輪完成，等待間隔後開始下一輪...',
  error: '本輪出現錯誤，正在重試...',
};

/** 節點狀態圖標 */
function StageStatusIcon({ status }: { status: string }) {
  if (status === 'running') return <Loader2 className="w-3 h-3 animate-spin" />;
  if (status === 'judging') return <Gavel className="w-3 h-3 animate-pulse" />;
  if (status === 'passed') return <CheckCircle2 className="w-3 h-3" />;
  if (status === 'failed') return <XCircle className="w-3 h-3" />;
  if (status === 'retrying') return <AlertCircle className="w-3 h-3 animate-bounce" />;
  if (status === 'passed_with_warning') return <AlertCircle className="w-3 h-3" />;
  return null;
}

/**
 * AgentIterationFlow 組件 — 運行時顯示當前迭代的階段流程進度條。
 * @param state Agent 當前狀態，null 或未運行時返回 null
 */
export function AgentIterationFlow({ state }: Props) {
  if (!state || !state.running) {
    return null;
  }

  const stage = parseStage(state.status_message);
  const currentStageIdx = STAGES.findIndex((s) => s.key === stage);
  const stageStatus = state.current_stage_status || 'running';

  return (
    <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
        <span className="text-sm font-medium text-blue-300">
          第 {state.current_iteration + 1} 輪迭代 · 6 AI 串聯 + 評委把關
        </span>
        {state.best_strategy_id && (
          <span className="text-xs text-amber-400 ml-auto">
            f0 = DB最佳策略 #{state.best_strategy_id} (評分{state.best_score.toFixed(1)})
          </span>
        )}
      </div>

      {/* 階段流程指示器 */}
      <div className="flex items-center gap-0.5">
        {STAGES.map((s, idx) => {
          const Icon = s.icon;
          const isCurrent = idx === currentStageIdx;
          const isDone = idx < currentStageIdx;
          const isPending = idx > currentStageIdx;

          return (
            <div key={s.key} className="flex items-center flex-1">
              <div className={`flex items-center gap-1 px-1.5 py-1.5 rounded-md text-[11px] font-medium transition-all duration-300 ${
                isCurrent
                  ? `${s.color} bg-current/10 scale-105 shadow-sm`
                  : isDone
                  ? 'text-green-400 bg-green-500/5'
                  : 'text-muted bg-bg-base/30'
              }`}>
                {isCurrent && <StageStatusIcon status={stageStatus} />}
                {isDone && <CheckCircle2 className="w-3 h-3" />}
                {isPending && <Icon className="w-3 h-3 opacity-40" />}
                <span className="hidden sm:inline">{s.label}</span>
                {/* 評委圖標 */}
                {isCurrent && stageStatus === 'judging' && (
                  <Gavel className="w-2.5 h-2.5 text-amber-400" />
                )}
              </div>
              {idx < STAGES.length - 1 && (
                <div className={`h-0.5 flex-1 mx-0.5 rounded transition-colors ${
                  isDone ? 'bg-green-500/30' : 'bg-border'
                }`} />
              )}
            </div>
          );
        })}
      </div>

      {/* 當前階段描述 + 評委狀態 */}
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-blue-300/70">
          {STAGE_DESCRIPTIONS[stage] ?? state.status_message}
        </span>
        {stageStatus === 'judging' && (
          <span className="flex items-center gap-1 text-amber-400">
            <Gavel className="w-3 h-3" />
            評委評分中...
          </span>
        )}
        {stageStatus === 'retrying' && (
          <span className="flex items-center gap-1 text-orange-400">
            <AlertCircle className="w-3 h-3" />
            評委未通過，重試中...
          </span>
        )}
      </div>
    </div>
  );
}
