/**
 * @file StrategyManager 組件 — 策略管理面板，
 * 支持保存/載入/刪除策略，以及選擇多個策略（最多 3 個）進行對比。
 */
'use client';

import { useState, useCallback } from 'react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Save, Trash2, Loader2, FolderOpen, GitCompare, AlertTriangle } from 'lucide-react';
import type {
  ScreenerCriteriaDto,
  BacktestConfigDto,
  BacktestResultDto,
  SavedStrategySummaryDto,
  SavedStrategyDetailDto,
} from '@/lib/api/types';

/** StrategyManager 組件屬性 */
interface StrategyManagerProps {
  /** 當前選股條件 */
  criteria: ScreenerCriteriaDto;
  /** 當前回測配置 */
  config: BacktestConfigDto;
  /** 當前回測結果 */
  result: BacktestResultDto | null;
  /** 載入策略回調（傳入條件、配置和結果） */
  onLoadStrategy: (criteria: ScreenerCriteriaDto, config: BacktestConfigDto, result: BacktestResultDto | null) => void;
  /** 策略對比回調，傳入選中的策略詳情列表 */
  onCompareStrategies?: (details: SavedStrategyDetailDto[]) => void;
}

/**
 * StrategyManager 組件 — 策略管理面板。
 * 通過 SWR 加載策略列表，支持保存當前策略、載入歷史策略、刪除策略和選擇對比。
 * @param criteria 當前選股條件
 * @param config 當前回測配置
 * @param result 當前回測結果
 * @param onLoadStrategy 載入策略回調
 * @param onCompareStrategies 對比策略回調
 */
export function StrategyManager({ criteria, config, result, onLoadStrategy, onCompareStrategies }: StrategyManagerProps) {
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [strategyName, setStrategyName] = useState('');
  const [saving, setSaving] = useState(false);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SavedStrategySummaryDto | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [compareIds, setCompareIds] = useState<Set<number>>(new Set());
  const [comparing, setComparing] = useState(false);

  const { data: strategies, mutate: reloadStrategies } = useSWR(
    '/backtest/strategies',
    () => api.listStrategies(),
    { revalidateOnFocus: false }
  );

  const handleSave = useCallback(async () => {
    if (!strategyName.trim()) {
      setError('请输入策略名称');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.saveStrategy({
        name: strategyName.trim(),
        criteria,
        config,
        result,
      });
      setShowSaveDialog(false);
      setStrategyName('');
      reloadStrategies();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }, [strategyName, criteria, config, result, reloadStrategies]);

  const handleLoad = useCallback(async (id: number) => {
    setLoadingId(id);
    setError(null);
    try {
      const detail = await api.getStrategy(id);
      onLoadStrategy(detail.criteria, detail.config, detail.result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingId(null);
    }
  }, [onLoadStrategy]);

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deleteStrategy(deleteTarget.id);
      setDeleteTarget(null);
      reloadStrategies();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeleting(false);
    }
  }, [deleteTarget, reloadStrategies]);

  const toggleCompare = useCallback((id: number) => {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < 3) {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleCompare = useCallback(async () => {
    if (compareIds.size < 2 || !onCompareStrategies) return;
    setComparing(true);
    setError(null);
    try {
      const details = await Promise.all(
        Array.from(compareIds).map((id) => api.getStrategy(id))
      );
      onCompareStrategies(details);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setComparing(false);
    }
  }, [compareIds, onCompareStrategies]);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderOpen className="w-4 h-4" />
            策略管理
          </CardTitle>
          <Button
            size="sm"
            onClick={() => { setStrategyName(`策略 ${new Date().toLocaleDateString('zh-CN')}`); setShowSaveDialog(true); }}
            disabled={!result}
            title={result ? '保存当前策略和回测结果' : '请先运行回测'}
          >
            <Save className="w-3 h-3 mr-1" />
            保存
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {error && <div className="text-xs text-down">{error}</div>}

          {/* 策略列表 */}
          {!strategies || strategies.length === 0 ? (
            <div className="text-center text-muted text-sm py-6">
              暂无保存的策略
              <div className="text-xs mt-1">运行回测后点击「保存」记录策略</div>
            </div>
          ) : (
            <>
              <div className="space-y-1.5 max-h-72 overflow-auto pr-1">
                {strategies.map((s: SavedStrategySummaryDto) => (
                  <div
                    key={s.id}
                    className={`flex items-center gap-2 rounded-md border p-2 transition-colors cursor-pointer ${
                      compareIds.has(s.id)
                        ? 'border-accent bg-accent/10'
                        : 'border-border-subtle hover:bg-bg-hover'
                    }`}
                    onClick={() => handleLoad(s.id)}
                  >
                    {/* 對比選擇框 */}
                    <input
                      type="checkbox"
                      checked={compareIds.has(s.id)}
                      onChange={(e) => { e.stopPropagation(); toggleCompare(s.id); }}
                      onClick={(e) => e.stopPropagation()}
                      className="accent-accent shrink-0"
                      title={compareIds.size >= 3 && !compareIds.has(s.id) ? '最多選擇3個' : '加入對比'}
                      disabled={compareIds.size >= 3 && !compareIds.has(s.id)}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-slate-200 truncate">{s.name}</div>
                      <div className="text-xs text-muted">
                        {new Date(s.createdAt).toLocaleString('zh-CN')}
                      </div>
                    </div>
                    {loadingId === s.id ? (
                      <Loader2 className="w-4 h-4 text-accent animate-spin shrink-0" />
                    ) : (
                      <button
                        onClick={(e) => { e.stopPropagation(); setDeleteTarget(s); }}
                        className="text-muted hover:text-down p-1 shrink-0"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* 對比按鈕 */}
              {onCompareStrategies && (
                <div className="flex items-center justify-between pt-2 border-t border-border-subtle">
                  <span className="text-xs text-muted">
                    已選 {compareIds.size}/3 {compareIds.size > 0 && '進行對比'}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleCompare}
                    disabled={compareIds.size < 2 || comparing}
                  >
                    {comparing ? (
                      <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    ) : (
                      <GitCompare className="w-3 h-3 mr-1" />
                    )}
                    策略對比
                  </Button>
                </div>
              )}
            </>
          )}

          {/* 保存對話框（內嵌） */}
          {showSaveDialog && (
            <div className="rounded-md border border-accent/30 bg-bg-card p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-accent">保存当前策略</span>
                <button onClick={() => setShowSaveDialog(false)} className="text-muted hover:text-slate-200 text-xs">取消</button>
              </div>
              <Input
                value={strategyName}
                onChange={(e) => setStrategyName(e.target.value)}
                placeholder="输入策略名称"
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); }}
              />
              <Button size="sm" onClick={handleSave} disabled={saving || !strategyName.trim()} className="w-full">
                {saving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
                确认保存
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 刪除確認框 */}
      {deleteTarget && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-96 rounded-lg border border-border bg-bg-panel shadow-xl p-5 space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-down/15 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5 text-down" />
              </div>
              <div className="flex-1">
                <h3 className="text-base font-semibold text-slate-100">确认删除策略？</h3>
                <p className="text-sm text-muted mt-1">
                  将永久删除策略「<span className="text-slate-200">{deleteTarget.name}</span>」及其所有回测结果数据，此操作不可撤销。
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={deleting}>取消</Button>
              <Button variant="danger" onClick={handleDelete} disabled={deleting}>
                {deleting ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Trash2 className="w-4 h-4 mr-1" />}
                确认删除
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
