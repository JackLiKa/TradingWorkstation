/**
 * @file AgentWorkflowGraph 組件 — AI 工作流圖譜，
 * 以水平節點排列形式展示 7 個 AI 節點的執行狀態、評委結果和連接關係，
 * 支持點擊節點查看詳細輸出。
 */
'use client';

import { useState } from 'react';
import {
  Loader2, Brain, Lightbulb, FlaskConical, Bot, PenLine,
  CheckCircle2, XCircle, AlertCircle, Gavel, Newspaper, Filter,
  Clock, ChevronRight, ChevronDown, Activity,
} from 'lucide-react';
import type { AgentState, StageResult } from '@/lib/api/types';

interface Props {
  state: AgentState | null;
  /** 當前迭代各階段結果（從 history 最新迭代獲取） */
  currentStageResults?: StageResult[];
}

/** 節點定義 */
interface NodeDef {
  id: string;
  label: string;
  icon: typeof Brain;
  color: string;
  isAI: boolean;
  hasJudge: boolean;
}

const NODES: NodeDef[] = [
  { id: 'market_news',       label: '行情新聞',   icon: Newspaper,      color: 'text-cyan-400',   isAI: true,  hasJudge: true },
  { id: 'industry_analysis', label: '行業篩選',   icon: Filter,         color: 'text-teal-400',   isAI: true,  hasJudge: true },
  { id: 'market_analysis',   label: '行情分析',   icon: Brain,          color: 'text-blue-400',   isAI: true,  hasJudge: true },
  { id: 'strategy_generation', label: '策略生成', icon: Lightbulb,      color: 'text-purple-400', isAI: true,  hasJudge: true },
  { id: 'backtest',          label: '回測運行',   icon: FlaskConical,   color: 'text-orange-400', isAI: false, hasJudge: false },
  { id: 'backtest_reflection', label: '回測反思', icon: Bot,            color: 'text-amber-400',  isAI: true,  hasJudge: true },
  { id: 'prompt_generation', label: '提示詞生成', icon: PenLine,        color: 'text-green-400',  isAI: true,  hasJudge: true },
];

/** 節點狀態 */
type NodeStatus = 'pending' | 'running' | 'judging' | 'passed' | 'failed' | 'retrying' | 'passed_with_warning';

/** 從 state 解析每個節點的狀態 */
function getNodeStatuses(state: AgentState | null, stageResults?: StageResult[]): Record<string, NodeStatus> {
  const statuses: Record<string, NodeStatus> = {};
  for (const n of NODES) {
    statuses[n.id] = 'pending';
  }
  if (!state || !state.running) return statuses;

  // 從 stage_results 獲取已完成節點的狀態
  if (stageResults) {
    for (const sr of stageResults) {
      if (sr.judge_passed) {
        statuses[sr.stage_name] = 'passed';
      } else if (sr.error) {
        statuses[sr.stage_name] = 'failed';
      } else if (sr.attempts > 1 && !sr.judge_passed) {
        statuses[sr.stage_name] = 'retrying';
      } else {
        statuses[sr.stage_name] = 'passed';
      }
    }
  }

  // 當前節點狀態
  const currentStage = state.current_stage;
  const currentStatus = state.current_stage_status as NodeStatus;
  if (currentStage && statuses[currentStage] === 'pending') {
    statuses[currentStage] = currentStatus || 'running';
  }

  // 回測節點：如果當前是 backtest_reflection，說明回測已完成
  if (statuses['backtest_reflection'] === 'running' || statuses['backtest_reflection'] === 'judging') {
    statuses['backtest'] = 'passed';
  }

  return statuses;
}

/** 節點狀態圖標 */
function StatusIcon({ status }: { status: NodeStatus }) {
  switch (status) {
    case 'running': return <Loader2 className="w-3 h-3 animate-spin" />;
    case 'judging': return <Gavel className="w-3 h-3 animate-pulse" />;
    case 'passed': return <CheckCircle2 className="w-3 h-3" />;
    case 'failed': return <XCircle className="w-3 h-3" />;
    case 'retrying': return <AlertCircle className="w-3 h-3 animate-bounce" />;
    case 'passed_with_warning': return <AlertCircle className="w-3 h-3" />;
    default: return null;
  }
}

/** 節點狀態顏色 */
function statusBgColor(status: NodeStatus): string {
  switch (status) {
    case 'running': return 'bg-blue-500/15 border-blue-500/40';
    case 'judging': return 'bg-amber-500/15 border-amber-500/40';
    case 'passed': return 'bg-green-500/10 border-green-500/30';
    case 'failed': return 'bg-red-500/15 border-red-500/40';
    case 'retrying': return 'bg-orange-500/15 border-orange-500/40';
    case 'passed_with_warning': return 'bg-amber-500/10 border-amber-500/30';
    default: return 'bg-bg-base/30 border-border';
  }
}

/** 單個節點卡片 */
function WorkflowNode({
  node, status, result, onClick, isSelected,
}: {
  node: NodeDef;
  status: NodeStatus;
  result?: StageResult;
  onClick: () => void;
  isSelected: boolean;
}) {
  const Icon = node.icon;
  const isActive = status !== 'pending';

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        onClick={onClick}
        disabled={!isActive && !result}
        className={`relative flex flex-col items-center gap-1 px-3 py-2 rounded-lg border transition-all duration-300 min-w-[90px] ${
          statusBgColor(status)
        } ${isSelected ? 'ring-2 ring-accent/50 scale-105' : ''} ${
          isActive ? 'cursor-pointer hover:scale-105' : 'opacity-50 cursor-default'
        }`}
      >
        <div className="flex items-center gap-1">
          <Icon className={`w-4 h-4 ${isActive ? node.color : 'text-muted'}`} />
          {node.hasJudge && status === 'judging' && (
            <Gavel className="w-3 h-3 text-amber-400" />
          )}
        </div>
        <span className={`text-[11px] font-medium ${isActive ? 'text-fg' : 'text-muted'}`}>
          {node.label}
        </span>
        <div className={`flex items-center gap-0.5 text-[10px] ${
          status === 'passed' ? 'text-green-400' :
          status === 'failed' ? 'text-red-400' :
          status === 'retrying' ? 'text-orange-400' :
          status === 'judging' ? 'text-amber-400' :
          status === 'running' ? 'text-blue-400' :
          'text-muted'
        }`}>
          <StatusIcon status={status} />
          {result && (
            <span className="ml-1">
              {result.duration_ms > 1000
                ? `${(result.duration_ms / 1000).toFixed(1)}s`
                : `${result.duration_ms}ms`}
            </span>
          )}
        </div>
      </button>

      {/* 評委徽章 */}
      {node.hasJudge && result && (
        <div className={`flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-full border ${
          result.judge_passed
            ? 'border-green-500/30 bg-green-500/10 text-green-400'
            : 'border-orange-500/30 bg-orange-500/10 text-orange-400'
        }`}>
          <Gavel className="w-2 h-2" />
          {result.judge_score.toFixed(0)}
          {result.attempts > 1 && <span className="ml-0.5">×{result.attempts}</span>}
        </div>
      )}
    </div>
  );
}

/** 評委節點（AI 節點之間的小連接） */
function JudgeConnector({ status }: { status: NodeStatus }) {
  if (status === 'judging') {
    return (
      <div className="flex items-center mx-0.5">
        <Gavel className="w-3 h-3 text-amber-400 animate-pulse" />
      </div>
    );
  }
  if (status === 'passed' || status === 'passed_with_warning') {
    return (
      <div className="flex items-center mx-0.5">
        <CheckCircle2 className="w-3 h-3 text-green-400/60" />
      </div>
    );
  }
  if (status === 'retrying') {
    return (
      <div className="flex items-center mx-0.5">
        <AlertCircle className="w-3 h-3 text-orange-400 animate-bounce" />
      </div>
    );
  }
  if (status === 'failed') {
    return (
      <div className="flex items-center mx-0.5">
        <XCircle className="w-3 h-3 text-red-400/60" />
      </div>
    );
  }
  return <ChevronRight className="w-3 h-3 text-border mx-0.5" />;
}

/**
 * AgentWorkflowGraph 組件 — AI 工作流圖譜主體。
 * @param state Agent 當前狀態
 * @param currentStageResults 當前迭代各階段結果（從 history 最新迭代獲取）
 */
export function AgentWorkflowGraph({ state, currentStageResults }: Props) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const statuses = getNodeStatuses(state, currentStageResults);

  // 找到選中節點的結果
  const selectedResult = currentStageResults?.find(sr => sr.stage_name === selectedNode);
  const selectedNodeDef = NODES.find(n => n.id === selectedNode);

  return (
    <div className="rounded-lg border border-border bg-bg-base/30 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-4 h-4 text-accent" />
        <span className="text-sm font-medium">AI 工作流圖譜</span>
        <span className="text-xs text-muted ml-auto">
          {state?.running ? `第 ${state.current_iteration + 1} 輪進行中` : '空閒'}
        </span>
      </div>

      {/* 工作流圖譜 — 水平排列 */}
      <div className="flex items-start gap-0 overflow-x-auto pb-2">
        {NODES.map((node, idx) => {
          const nodeStatus = statuses[node.id];
          const nodeResult = currentStageResults?.find(sr => sr.stage_name === node.id);
          return (
            <div key={node.id} className="flex items-center flex-shrink-0">
              <WorkflowNode
                node={node}
                status={nodeStatus}
                result={nodeResult}
                onClick={() => setSelectedNode(selectedNode === node.id ? null : node.id)}
                isSelected={selectedNode === node.id}
              />
              {idx < NODES.length - 1 && (
                <JudgeConnector status={nodeStatus} />
              )}
            </div>
          );
        })}
      </div>

      {/* 節點詳情面板 */}
      {selectedNode && selectedResult && selectedNodeDef && (
        <NodeDetailPanel node={selectedNodeDef} result={selectedResult} />
      )}

      {/* 圖例 */}
      <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border text-[10px] text-muted">
        <span className="flex items-center gap-1"><Loader2 className="w-2.5 h-2.5" />運行中</span>
        <span className="flex items-center gap-1"><Gavel className="w-2.5 h-2.5" />評委中</span>
        <span className="flex items-center gap-1"><CheckCircle2 className="w-2.5 h-2.5" />通過</span>
        <span className="flex items-center gap-1"><AlertCircle className="w-2.5 h-2.5" />重試</span>
        <span className="flex items-center gap-1"><XCircle className="w-2.5 h-2.5" />失敗</span>
        <span className="ml-auto">點擊節點查看詳情</span>
      </div>
    </div>
  );
}

/** 節點詳情面板 — 顯示輸出、評委結果、耗時等 */
function NodeDetailPanel({ node, result }: { node: NodeDef; result: StageResult }) {
  const [showFullOutput, setShowFullOutput] = useState(false);
  const Icon = node.icon;

  return (
    <div className="mt-3 rounded-lg border border-accent/20 bg-accent/5 p-3 space-y-2">
      {/* 標題 */}
      <div className="flex items-center gap-2">
        <Icon className={`w-4 h-4 ${node.color}`} />
        <span className="text-sm font-medium">{node.label}</span>
        <span className="text-xs text-muted">節點詳情</span>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <span className="flex items-center gap-1 text-muted">
            <Clock className="w-3 h-3" />
            {result.duration_ms > 1000 ? `${(result.duration_ms / 1000).toFixed(1)}s` : `${result.duration_ms}ms`}
          </span>
          {result.attempts > 1 && (
            <span className="text-orange-400">重試 {result.attempts} 次</span>
          )}
        </div>
      </div>

      {/* 評委結果 */}
      <div className={`flex items-center gap-2 text-xs rounded border px-2 py-1.5 ${
        result.judge_passed
          ? 'border-green-500/20 bg-green-500/5'
          : 'border-orange-500/20 bg-orange-500/5'
      }`}>
        <Gavel className={`w-3.5 h-3.5 ${result.judge_passed ? 'text-green-400' : 'text-orange-400'}`} />
        <span className="font-medium">評委評分: {result.judge_score.toFixed(1)}</span>
        <span className={result.judge_passed ? 'text-green-400' : 'text-orange-400'}>
          {result.judge_passed ? '通過' : '未通過'}
        </span>
        {result.judge_feedback && (
          <span className="text-muted truncate flex-1" title={result.judge_feedback}>
            {result.judge_feedback}
          </span>
        )}
      </div>

      {/* 錯誤信息 */}
      {result.error && (
        <div className="flex items-start gap-2 text-xs text-red-400 bg-red-500/5 border border-red-500/20 rounded p-2">
          <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          <span className="break-all">{result.error}</span>
        </div>
      )}

      {/* 輸出內容 */}
      {result.output && (
        <div className="text-xs">
          <button
            onClick={() => setShowFullOutput(!showFullOutput)}
            className="flex items-center gap-1 text-muted hover:text-fg transition-colors mb-1"
          >
            {showFullOutput ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            AI 輸出 ({result.output.length} 字符)
          </button>
          {showFullOutput && (
            <pre className="whitespace-pre-wrap break-words text-fg/80 bg-bg-base/50 rounded p-2 max-h-60 overflow-y-auto text-[11px] leading-relaxed">
              {result.output}
            </pre>
          )}
          {!showFullOutput && (
            <p className="text-muted truncate">{result.output.slice(0, 120)}...</p>
          )}
        </div>
      )}
    </div>
  );
}
