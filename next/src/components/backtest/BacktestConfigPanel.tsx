/**
 * @file BacktestConfigPanel 組件 — 回測配置面板，
 * 包含日期範圍、調倉間隔、持倉數、初始資金、手續費、止損止盈等參數。
 */
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import type { BacktestConfigDto, ScreenerCriteriaDto } from '@/lib/api/types';
import { Play, Loader2 } from 'lucide-react';

/** BacktestConfigPanel 組件屬性 */
interface Props {
  /** 回測配置 */
  config: BacktestConfigDto;
  /** 配置變更回調 */
  onChange: (config: BacktestConfigDto) => void;
  /** 運行回測回調 */
  onRun: () => void;
  /** 是否正在運行回測 */
  loading?: boolean;
  /** 是否自動保存回測結果到數據庫 */
  autoSave?: boolean;
  /** 切換自動保存開關 */
  onToggleAutoSave?: (value: boolean) => void;
}

/**
 * BacktestConfigPanel 組件 — 回測參數配置面板。
 * @param config 回測配置
 * @param onChange 配置變更回調
 * @param onRun 運行回測回調
 * @param loading 是否運行中
 * @param autoSave 是否自動保存
 * @param onToggleAutoSave 切換自動保存
 */
export function BacktestConfigPanel({ config, onChange, onRun, loading, autoSave = true, onToggleAutoSave }: Props) {
  const update = <K extends keyof BacktestConfigDto>(key: K, value: BacktestConfigDto[K]) =>
    onChange({ ...config, [key]: value });

  return (
    <Card>
      <CardHeader>
        <CardTitle>回测配置</CardTitle>
        <Button size="sm" onClick={onRun} disabled={loading}>
          {loading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />}
          {loading ? '运行中...' : '运行回测'}
        </Button>
      </CardHeader>
      <CardContent>
        {/* 自動保存開關 */}
        {onToggleAutoSave && (
          <label className="flex items-center gap-2 cursor-pointer mb-3 p-2 rounded-md bg-bg-hover border border-border-subtle">
            <input
              type="checkbox"
              checked={autoSave}
              onChange={(e) => onToggleAutoSave(e.target.checked)}
              className="w-4 h-4 rounded border-border accent-accent"
            />
            <span className="text-xs text-slate-200">回測完成後自動保存到數據庫（供 AI 優化參考）</span>
          </label>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="开始日期">
            <Input type="date" value={config.startDate} onChange={(e) => update('startDate', e.target.value)} />
          </Field>
          <Field label="结束日期">
            <Input type="date" value={config.endDate} onChange={(e) => update('endDate', e.target.value)} />
          </Field>
          <Field label="调仓间隔(日)">
            <Input type="number" value={config.rebalanceInterval} onChange={(e) => update('rebalanceInterval', Number(e.target.value))} />
          </Field>
          <Field label="持有期(日)">
            <Input type="number" value={config.holdingPeriod} onChange={(e) => update('holdingPeriod', Number(e.target.value))} />
          </Field>
          <Field label="最大持仓数">
            <Input type="number" value={config.maxPositions} onChange={(e) => update('maxPositions', Number(e.target.value))} />
          </Field>
          <Field label="初始资金">
            <Input type="number" value={config.initialCapital} onChange={(e) => update('initialCapital', Number(e.target.value))} />
          </Field>
          <Field label="手续费(bp)">
            <Input type="number" step="0.5" value={config.commissionBps} onChange={(e) => update('commissionBps', Number(e.target.value))} />
          </Field>
          <Field label="止损(%)">
            <Input type="number" value={config.stopLossPct ?? ''} onChange={(e) => update('stopLossPct', e.target.value ? Number(e.target.value) : null)} />
          </Field>
          <Field label="止盈(%)">
            <Input type="number" value={config.takeProfitPct ?? ''} onChange={(e) => update('takeProfitPct', e.target.value ? Number(e.target.value) : null)} />
          </Field>
        </div>
      </CardContent>
    </Card>
  );
}

/** 單個表單字段組件（標籤 + 子元素） */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-muted">{label}</label>
      {children}
    </div>
  );
}
