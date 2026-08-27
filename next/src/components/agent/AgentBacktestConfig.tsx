/**
 * @file AgentBacktestConfig 組件 — 回測配置面板，
 * 支持手動調整回測日期區間（startDate/endDate），並校驗數據庫覆蓋範圍。
 * 同時可調整持倉數、調倉間隔等參數。
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { agentApi } from '@/lib/api/agent';
import type { AgentState } from '@/lib/api/types';
import { Calendar, Save, Loader2, AlertCircle, Info } from 'lucide-react';

/** AgentBacktestConfig 組件屬性 */
interface Props {
  /** Agent 當前狀態，用於讀取當前 config */
  state: AgentState | null;
  /** 啟動優化時傳遞的 config（由父組件管理） */
  onStartConfigChange?: (config: Record<string, unknown>) => void;
  /** 是否為啟動前的配置模式（true 時只更新父組件 state，不調用 /config API） */
  preStartMode?: boolean;
}

/**
 * AgentBacktestConfig 組件 — 回測日期區間和參數配置面板。
 * @param state Agent 當前狀態
 * @param onStartConfigChange 啟動前模式下的 config 變更回調
 * @param preStartMode 是否為啟動前配置模式
 */
export function AgentBacktestConfig({ state, onStartConfigChange, preStartMode = false }: Props) {
  // 獲取數據庫數據範圍
  const { data: dataRange } = useSWR(
    'agent-data-range',
    () => agentApi.getDataRange(),
    { refreshInterval: 60000, revalidateOnFocus: false }
  );

  const currentConfig = (state?.current_config ?? {}) as Record<string, unknown>;
  const earliest = dataRange?.earliestTradeDate ?? null;
  const latest = dataRange?.latestTradeDate ?? null;

  // 本地編輯狀態
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [maxPositions, setMaxPositions] = useState(5);
  const [rebalanceInterval, setRebalanceInterval] = useState(5);
  const [holdingPeriod, setHoldingPeriod] = useState(10);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // 從 state 同步當前 config 到本地編輯狀態
  useEffect(() => {
    if (currentConfig.startDate) setStartDate(String(currentConfig.startDate));
    if (currentConfig.endDate) setEndDate(String(currentConfig.endDate));
    if (currentConfig.maxPositions) setMaxPositions(Number(currentConfig.maxPositions));
    if (currentConfig.rebalanceInterval) setRebalanceInterval(Number(currentConfig.rebalanceInterval));
    if (currentConfig.holdingPeriod) setHoldingPeriod(Number(currentConfig.holdingPeriod));
  }, [currentConfig.startDate, currentConfig.endDate, currentConfig.maxPositions,
      currentConfig.rebalanceInterval, currentConfig.holdingPeriod]);

  // 校驗日期範圍
  const validateDates = useCallback((): string | null => {
    if (!startDate || !endDate) return '請填寫開始和結束日期';
    if (startDate > endDate) return `開始日期 (${startDate}) 不能晚於結束日期 (${endDate})`;
    if (earliest && startDate < earliest) return `開始日期 (${startDate}) 早於數據庫最早交易日 (${earliest})`;
    if (latest && endDate > latest) return `結束日期 (${endDate}) 晚於數據庫最新交易日 (${latest})`;
    return null;
  }, [startDate, endDate, earliest, latest]);

  // 實時通知父組件（啟動前模式）
  useEffect(() => {
    if (preStartMode && onStartConfigChange) {
      const err = validateDates();
      if (!err) {
        onStartConfigChange({
          ...currentConfig,
          startDate,
          endDate,
          maxPositions,
          rebalanceInterval,
          holdingPeriod,
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate, maxPositions, rebalanceInterval, holdingPeriod, preStartMode]);

  const handleSave = async () => {
    const err = validateDates();
    if (err) {
      setError(err);
      return;
    }
    setError(null);
    setSaving(true);
    setSaved(false);
    try {
      const newConfig = {
        ...currentConfig,
        startDate,
        endDate,
        maxPositions,
        rebalanceInterval,
        holdingPeriod,
      };
      await agentApi.updateConfig(newConfig);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const validationError = validateDates();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-accent" />
          回測配置
        </CardTitle>
        {!preStartMode && (
          <Button size="sm" onClick={handleSave} disabled={saving || !!validationError}>
            {saving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
            {saving ? '保存中...' : saved ? '已保存' : '保存配置'}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {/* 數據庫覆蓋範圍提示 */}
        {earliest && latest ? (
          <div className="flex items-center gap-2 text-xs text-muted bg-bg-hover rounded p-2 mb-3">
            <Info className="w-3.5 h-3.5 flex-shrink-0" />
            <span>
              數據庫覆蓋範圍：<span className="text-slate-300">{earliest}</span> ~ <span className="text-slate-300">{latest}</span>
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 rounded p-2 mb-3">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>無法獲取數據庫日期範圍，請確保後端服務正常運行</span>
          </div>
        )}

        {/* 日期區間 */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="text-xs text-muted mb-1 block">回測開始日期</label>
            <Input
              type="date"
              value={startDate}
              min={earliest ?? undefined}
              max={latest ?? undefined}
              onChange={(e) => setStartDate(e.target.value)}
              className="text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-muted mb-1 block">回測結束日期</label>
            <Input
              type="date"
              value={endDate}
              min={earliest ?? undefined}
              max={latest ?? undefined}
              onChange={(e) => setEndDate(e.target.value)}
              className="text-sm"
            />
          </div>
        </div>

        {/* 參數配置 */}
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div>
            <label className="text-xs text-muted mb-1 block">最大持倉數</label>
            <Input
              type="number"
              min={1}
              max={20}
              value={maxPositions}
              onChange={(e) => setMaxPositions(Number(e.target.value))}
              className="text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-muted mb-1 block">調倉間隔（天）</label>
            <Input
              type="number"
              min={1}
              max={60}
              value={rebalanceInterval}
              onChange={(e) => setRebalanceInterval(Number(e.target.value))}
              className="text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-muted mb-1 block">持有天數</label>
            <Input
              type="number"
              min={1}
              max={120}
              value={holdingPeriod}
              onChange={(e) => setHoldingPeriod(Number(e.target.value))}
              className="text-sm"
            />
          </div>
        </div>

        {/* 校驗錯誤 */}
        {validationError && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 rounded p-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {validationError}
          </div>
        )}

        {/* 保存成功提示 */}
        {saved && !validationError && (
          <div className="flex items-center gap-2 text-sm text-green-400 bg-green-500/10 rounded p-2">
            <Save className="w-4 h-4" />
            配置已更新，下一輪迭代將使用新的回測參數
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 rounded p-2 mt-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
