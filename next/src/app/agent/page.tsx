/**
 * @file AgentPage AI 策略優化頁 — Agent 功能主頁面，
 * 展示優化控制面板、迭代流程、工作流圖譜、系統監控、評分趨勢和優化歷史。
 * 通過 SWR 輪詢 Agent 服務 (8100) 的狀態和歷史接口。
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { agentApi } from '@/lib/api/agent';
import type { AgentState, AgentHistory, AgentModelStatus } from '@/lib/api/types';
import { Play, Square, RefreshCw, Loader2, Bot, Activity, TrendingUp, Award, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';
import { AgentIterationCard } from '@/components/agent/AgentIterationCard';
import { AgentStatusPanel } from '@/components/agent/AgentStatusPanel';
import { AgentIterationFlow } from '@/components/agent/AgentIterationFlow';
import { AgentWorkflowGraph } from '@/components/agent/AgentWorkflowGraph';
import { AgentMonitorPanel } from '@/components/agent/AgentMonitorPanel';
import { AgentScoreTrend } from '@/components/agent/AgentScoreTrend';
import { AgentModelCard } from '@/components/agent/AgentModelCard';
import { AgentProviderSelector } from '@/components/agent/AgentProviderSelector';
import { AgentBacktestConfig } from '@/components/agent/AgentBacktestConfig';

/** Agent 狀態輪詢間隔（運行時 2 秒） */
const STATUS_REFETCH_MS = 2000;

/**
 * AgentPage AI 策略優化頁組件。
 * 管理啟動/停止/檢查模型等操作，輪詢 agent 狀態（運行時 2s，空閒時 10s）和歷史記錄。
 */
export default function AgentPage() {
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [confirmStop, setConfirmStop] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkingModel, setCheckingModel] = useState(false);
  const [startConfig, setStartConfig] = useState<Record<string, unknown> | null>(null);

  // 輪詢 agent 狀態（運行時 2s，空閒時 10s）
  const { data: state, mutate: refreshState } = useSWR<AgentState>(
    'agent-status',
    () => agentApi.status(),
    { refreshInterval: (latest) => (latest?.running ? STATUS_REFETCH_MS : 10000), revalidateOnFocus: false }
  );

  // 輪詢歷史記錄
  const { data: history, mutate: refreshHistory, isValidating: historyValidating } = useSWR<AgentHistory>(
    'agent-history',
    () => agentApi.history(50),
    { refreshInterval: (latest) => {
      // 有新迭代時刷新
      const stateRunning = state?.running;
      return stateRunning ? 5000 : 0;
    }, revalidateOnFocus: false }
  );

  // 模型狀態
  const { data: health, mutate: refreshHealth } = useSWR(
    'agent-health',
    () => agentApi.health().catch(() => null),
    { refreshInterval: 30000, revalidateOnFocus: false }
  );

  const handleStart = useCallback(async () => {
    setStarting(true);
    setError(null);
    try {
      await agentApi.start(undefined, startConfig ?? undefined);
      await refreshState();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  }, [refreshState, startConfig]);

  const handleStop = useCallback(async () => {
    setStopping(true);
    setConfirmStop(false);
    try {
      await agentApi.stop();
      await refreshState();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStopping(false);
    }
  }, [refreshState]);

  const handleCheckModel = useCallback(async () => {
    setCheckingModel(true);
    try {
      await agentApi.checkModel();
      await refreshHealth();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCheckingModel(false);
    }
  }, [refreshHealth]);

  const modelStatus = health?.model;
  const allModels = health?.models ?? [];
  const isRunning = state?.running ?? false;
  const iterations = history?.iterations ?? [];

  return (
    <div className="space-y-4">
      {/* 標題 + 運行狀態 */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-accent" />
          <h1 className="text-lg font-semibold">AI 策略優化 Agent</h1>
          {isRunning && (
            <span className="flex items-center gap-1 text-xs text-green-500 bg-green-500/10 px-2 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
              運行中
            </span>
          )}
        </div>
      </div>

      {/* 模型狀態卡片 — 顯示全部模型檢查結果，支持手動檢查 */}
      <AgentModelCard
        modelStatus={modelStatus}
        allModels={allModels}
        checking={checkingModel}
        onCheck={handleCheckModel}
      />

      {/* 每階段供應商選擇 */}
      <AgentProviderSelector />

      {/* 回測配置（啟動前可調整日期區間，運行中可隨時更新） */}
      <AgentBacktestConfig
        state={state ?? null}
        preStartMode={!isRunning}
        onStartConfigChange={setStartConfig}
      />

      {/* 控制面板 */}
      <Card>
        <CardHeader>
          <CardTitle>優化控制</CardTitle>
          <div className="flex gap-2">
            {!isRunning ? (
              <Button size="sm" onClick={handleStart} disabled={starting || !modelStatus?.available}>
                {starting ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />}
                {starting ? '啟動中...' : '啟動優化'}
              </Button>
            ) : (
              <Button variant="danger" size="sm" onClick={() => setConfirmStop(true)} disabled={stopping}>
                {stopping ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Square className="w-3 h-3 mr-1" />}
                {stopping ? '停止中...' : '停止'}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {/* 停止確認彈窗 */}
          {confirmStop && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setConfirmStop(false)}>
              <div className="bg-card border border-border rounded-lg p-6 max-w-sm w-full mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-red-500/15 flex items-center justify-center">
                    <AlertCircle className="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-slate-100">確認停止優化？</h3>
                    <p className="text-xs text-muted mt-0.5">當前迭代將被中斷，已完成的迭代結果會保留</p>
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" size="sm" onClick={() => setConfirmStop(false)}>
                    取消
                  </Button>
                  <Button variant="danger" size="sm" onClick={handleStop}>
                    <Square className="w-3 h-3 mr-1" />
                    確認停止
                  </Button>
                </div>
              </div>
            </div>
          )}
          {error && (
            <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 rounded p-2 mb-3">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}
          {modelStatus && !modelStatus.available && (
            <div className="flex items-center gap-2 text-sm text-amber-400 bg-amber-500/10 rounded p-2 mb-3">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {modelStatus.error || "所有免費模型不可用，AI 優化功能已關閉。請檢查 API Key 或點擊「檢查模型」"}
            </div>
          )}
          <AgentStatusPanel state={state ?? null} />

          {/* 迭代階段流程指示器（運行時顯示） */}
          <AgentIterationFlow state={state ?? null} />

          {/* AI 工作流圖譜（運行時顯示，展示各節點狀態和評委結果） */}
          {isRunning && (
            <AgentWorkflowGraph
              state={state ?? null}
              currentStageResults={state?.current_stage_results}
            />
          )}

          {/* 系統監控面板（始終顯示，展示節點統計、告警、AI 診斷） */}
          <AgentMonitorPanel />

          {/* 評分趨勢迷你圖（有歷史記錄時顯示） */}
          {iterations.length > 0 && (
            <AgentScoreTrend
              iterations={iterations}
              bestScore={state?.best_score ?? -999}
              bestIteration={state?.best_iteration ?? 0}
            />
          )}
        </CardContent>
      </Card>

      {/* 優化歷史 */}
      <Card>
        <CardHeader>
          <CardTitle>優化歷史 ({iterations.length} 輪)</CardTitle>
          <Button variant="outline" size="sm" onClick={() => refreshHistory()}>
            <RefreshCw className="w-3 h-3 mr-1" />
            刷新
          </Button>
        </CardHeader>
        <CardContent>
          {iterations.length === 0 ? (
            <div className="text-center py-8 text-muted text-sm">
              {historyValidating && !history ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  載入歷史記錄中...
                </span>
              ) : isRunning ? (
                `AI 正在進行第 ${(state?.current_iteration ?? 0) + 1} 輪優化，請稍候...`
              ) : (
                '尚未有優化記錄，點擊「啟動優化」開始'
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {iterations.map((it, idx) => (
                <AgentIterationCard
                  key={it.iteration}
                  iteration={it}
                  isBest={it.iteration === state?.best_iteration}
                  defaultExpanded={idx === 0}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
