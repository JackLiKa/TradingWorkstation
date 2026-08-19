/**
 * @file AgentProviderSelector 組件 — 每階段 LLM 供應商選擇面板。
 * 支持為每個 AI 階段獨立選擇供應商（DeepSeek/GLM/Qwen/Qoder/Devin/自動），
 * 並顯示當前可用供應商 + 默認路由 + 模型詳情。
 */
'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { agentApi } from '@/lib/api/agent';
import { Cpu, RotateCcw, Zap, DollarSign } from 'lucide-react';

/** AI 階段定義 */
const STAGES = [
  { name: 'market_news', label: 'AI 0 · 行情新聞' },
  { name: 'industry_analysis', label: 'AI 0.5 · 行業分析' },
  { name: 'market_analysis', label: 'AI 1 · 行情分析' },
  { name: 'strategy_generation', label: 'AI 2 · 策略生成 ★' },
  { name: 'backtest_reflection', label: 'AI 3 · 回測反思' },
  { name: 'prompt_generation', label: 'AI 4 · 提示詞生成' },
  { name: 'judge', label: 'Judge · 評委' },
  { name: 'monitor', label: 'Monitor · 監控' },
];

/** 供應商顯示配置 */
const PROVIDER_CONFIG: Record<string, { label: string; color: string }> = {
  'deepseek-pro':    { label: 'DeepSeek V4-Pro',    color: 'blue' },
  'deepseek-flash':  { label: 'DeepSeek V4-Flash',  color: 'cyan' },
  'glm-5.2':         { label: 'GLM-5.2',            color: 'purple' },
  'glm-flash':       { label: 'GLM-4-Flash (免費)', color: 'green' },
  'qwen':            { label: 'Qwen3.6',            color: 'orange' },
  'qoder':           { label: 'Qoder Lite (免費)',  color: 'gray' },
  'devin':           { label: 'Devin GLM-5.2',      color: 'gray' },
  '':                { label: '自動選擇',           color: 'default' },
};

export function AgentProviderSelector() {
  const { data: providers, mutate } = useSWR(
    'agent-providers',
    () => agentApi.getProviders(),
    { refreshInterval: 30000 }
  );
  const [updating, setUpdating] = useState<string | null>(null);

  const availableProviders = providers?.providers ?? [];
  const stagePrefs = providers?.stage_preferences ?? {};
  const stageDefaults = providers?.stage_defaults ?? {};
  const providerDetails = providers?.provider_details ?? {};

  const handleSetProvider = async (stageName: string, provider: string) => {
    setUpdating(stageName);
    try {
      await agentApi.setStageProvider({ stage_name: stageName, provider });
      await mutate();
    } catch (e) {
      console.error('設置供應商失敗:', e);
    } finally {
      setUpdating(null);
    }
  };

  const handleReset = async () => {
    setUpdating('reset');
    try {
      await agentApi.resetStageProviders();
      await mutate();
    } catch (e) {
      console.error('重置供應商失敗:', e);
    } finally {
      setUpdating(null);
    }
  };

  const getProviderLabel = (pid: string) =>
    PROVIDER_CONFIG[pid]?.label ?? pid;

  const isProviderAvailable = (pid: string) =>
    availableProviders.find((p) => p.provider === pid)?.available ?? false;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Cpu className="w-4 h-4" />
          每階段 LLM 供應商路由
        </CardTitle>
        <Button size="sm" variant="outline" onClick={handleReset} disabled={updating === 'reset'}>
          <RotateCcw className="w-3 h-3 mr-1" />
          重置為默認
        </Button>
      </CardHeader>
      <CardContent>
        {/* 可用供應商概覽 */}
        <div className="flex flex-wrap gap-2 mb-4">
          {availableProviders.map((p) => (
            <Badge key={p.provider} variant={p.available ? 'success' : 'danger'}>
              {getProviderLabel(p.provider)}
              {p.is_free && <DollarSign className="w-3 h-3 ml-1 inline" />}
              {p.available ? ' ✓' : ' ✗'}
            </Badge>
          ))}
          {availableProviders.length === 0 && (
            <span className="text-xs text-muted">載入中...</span>
          )}
        </div>

        {/* 每階段選擇器 */}
        <div className="space-y-2">
          {STAGES.map((stage) => {
            const userPref = stagePrefs[stage.name] ?? '';
            const defaultPref = stageDefaults[stage.name] ?? '';
            const current = userPref || defaultPref;
            const isUpdating = updating === stage.name;
            const isCustomized = !!userPref;
            return (
              <div key={stage.name} className="flex items-center gap-3">
                <div className="flex-1 text-sm text-slate-200">
                  {stage.label}
                  {!isCustomized && defaultPref && (
                    <span className="text-xs text-muted ml-2">
                      (默認: {getProviderLabel(defaultPref)})
                    </span>
                  )}
                </div>
                <Select
                  value={userPref}
                  onChange={(e) => handleSetProvider(stage.name, e.target.value)}
                  disabled={isUpdating}
                  className="w-48"
                >
                  <option value="">自動 ({getProviderLabel(defaultPref)})</option>
                  {Object.entries(PROVIDER_CONFIG)
                    .filter(([pid]) => pid !== '')
                    .map(([pid, cfg]) => (
                      <option
                        key={pid}
                        value={pid}
                        disabled={!isProviderAvailable(pid)}
                      >
                        {cfg.label}
                        {!isProviderAvailable(pid) ? ' (不可用)' : ''}
                      </option>
                    ))}
                </Select>
                {isUpdating && <span className="text-xs text-muted">更新中...</span>}
                {isCustomized && <Zap className="w-3 h-3 text-yellow-400" />}
              </div>
            );
          })}
        </div>

        {/* 供應商詳情 */}
        {Object.keys(providerDetails).length > 0 && (
          <div className="mt-4 pt-3 border-t border-border-subtle">
            <div className="text-xs font-semibold text-muted mb-2">供應商詳情</div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {Object.entries(providerDetails).map(([pid, detail]: [string, any]) => (
                <div key={pid} className="flex items-start gap-1">
                  <Badge
                    variant={isProviderAvailable(pid) ? 'success' : 'danger'}
                    className="text-xs shrink-0"
                  >
                    {detail.is_free ? '免費' : '付費'}
                  </Badge>
                  <div>
                    <div className="text-slate-300">{detail.display_name}</div>
                    <div className="text-muted">{detail.description}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-3 pt-3 border-t border-border-subtle text-xs text-muted">
          提示：選擇「自動」時使用各階段的默認供應商（性價比最優配置）。
          供應商不可用時自動降級。★ 標記的 AI 2 是最關鍵節點。
        </div>
      </CardContent>
    </Card>
  );
}
