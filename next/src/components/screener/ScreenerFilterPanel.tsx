/**
 * @file ScreenerFilterPanel 組件 — 選股篩選條件面板，
 * 包含價格區間、量額、區間收益、技術指標、信號排列、均線排列等全部篩選條件。
 */
'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import type { ScreenerCriteriaDto } from '@/lib/api/types';
import { Play, Download, Loader2 } from 'lucide-react';

/** ScreenerFilterPanel 組件屬性 */
interface Props {
  /** 當前篩選條件 */
  criteria: ScreenerCriteriaDto;
  /** 條件變更回調 */
  onChange: (criteria: ScreenerCriteriaDto) => void;
  /** 運行選股回調 */
  onRun: () => void;
  /** 導出 CSV 回調（可選） */
  onExport?: () => void;
  /** 是否正在運行選股 */
  running?: boolean;
}

/**
 * ScreenerFilterPanel 組件 — 選股篩選條件面板。
 * @param criteria 當前篩選條件
 * @param onChange 條件變更回調
 * @param onRun 運行選股回調
 * @param onExport 導出 CSV 回調
 * @param running 是否運行中
 */
export function ScreenerFilterPanel({ criteria, onChange, onRun, onExport, running }: Props) {
  const update = <K extends keyof ScreenerCriteriaDto>(key: K, value: ScreenerCriteriaDto[K]) =>
    onChange({ ...criteria, [key]: value });

  return (
    <Card>
      <CardHeader>
        <CardTitle>筛选条件</CardTitle>
        <div className="flex gap-2">
          {onExport && (
            <Button variant="outline" size="sm" onClick={onExport} disabled={running}>
              <Download className="w-3 h-3 mr-1" />
              导出 CSV
            </Button>
          )}
          <Button size="sm" onClick={onRun} disabled={running}>
            {running ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />}
            {running ? '运行中...' : '运行选股'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="基准日期">
            <Input type="date" value={criteria.asOfDate} onChange={(e) => update('asOfDate', e.target.value)} />
          </Field>
          <Field label="复权方式">
            <Select value={String(criteria.adjustflag)} onChange={(e) => update('adjustflag', Number(e.target.value))}>
              <option value={1}>后复权</option>
              <option value={2}>前复权</option>
              <option value={3}>不复权</option>
            </Select>
          </Field>
          <Field label="最大结果数">
            <Input type="number" value={criteria.maxResults ?? 100} onChange={(e) => update('maxResults', Number(e.target.value))} />
          </Field>
          <Field label="排序字段">
            <Select value={criteria.sortBy ?? 'score'} onChange={(e) => update('sortBy', e.target.value)}>
              <option value="score">综合评分</option>
              <option value="pct_change">涨跌幅</option>
              <option value="turn">换手率</option>
              <option value="amplitude">振幅</option>
              <option value="volume_ratio">量比</option>
              <option value="return_20">20日涨幅</option>
              <option value="return_60">60日涨幅</option>
              <option value="return_120">120日涨幅</option>
              <option value="rsi14">RSI14</option>
              <option value="macd_hist">MACD柱</option>
              <option value="boll_percent_b">BOLL%B</option>
            </Select>
          </Field>
        </div>

        <Section title="价格区间">
          <RangeField label="收盘价" min={criteria.minClose} max={criteria.maxClose}
            onMin={(v) => update('minClose', v)} onMax={(v) => update('maxClose', v)} />
          <RangeField label="涨跌幅%" min={criteria.minPctChange} max={criteria.maxPctChange}
            onMin={(v) => update('minPctChange', v)} onMax={(v) => update('maxPctChange', v)} />
          <RangeField label="换手率%" min={criteria.minTurn} max={criteria.maxTurn}
            onMin={(v) => update('minTurn', v)} onMax={(v) => update('maxTurn', v)} />
          <RangeField label="振幅%" min={criteria.minAmplitude} max={criteria.maxAmplitude}
            onMin={(v) => update('minAmplitude', v)} onMax={(v) => update('maxAmplitude', v)} />
        </Section>

        <Section title="量额">
          <Field label="最小成交量">
            <Input type="number" value={criteria.minVolume ?? ''} onChange={(e) => update('minVolume', e.target.value ? Number(e.target.value) : null)} />
          </Field>
          <Field label="最小成交额">
            <Input type="number" value={criteria.minAmount ?? ''} onChange={(e) => update('minAmount', e.target.value ? Number(e.target.value) : null)} />
          </Field>
          <RangeField label="量比" min={criteria.minVolumeRatio} max={criteria.maxVolumeRatio}
            onMin={(v) => update('minVolumeRatio', v)} onMax={(v) => update('maxVolumeRatio', v)} />
        </Section>

        <Section title="区间收益">
          <RangeField label="20日%" min={criteria.minReturn20} max={criteria.maxReturn20}
            onMin={(v) => update('minReturn20', v)} onMax={(v) => update('maxReturn20', v)} />
          <RangeField label="60日%" min={criteria.minReturn60} max={criteria.maxReturn60}
            onMin={(v) => update('minReturn60', v)} onMax={(v) => update('maxReturn60', v)} />
          <RangeField label="120日%" min={criteria.minReturn120} max={criteria.maxReturn120}
            onMin={(v) => update('minReturn120', v)} onMax={(v) => update('maxReturn120', v)} />
        </Section>

        <Section title="技术指标">
          <RangeField label="RSI14" min={criteria.minRsi14} max={criteria.maxRsi14}
            onMin={(v) => update('minRsi14', v)} onMax={(v) => update('maxRsi14', v)} />
          <RangeField label="K值" min={criteria.minKValue} max={criteria.maxKValue}
            onMin={(v) => update('minKValue', v)} onMax={(v) => update('maxKValue', v)} />
          <RangeField label="D值" min={criteria.minDValue} max={criteria.maxDValue}
            onMin={(v) => update('minDValue', v)} onMax={(v) => update('maxDValue', v)} />
          <RangeField label="J值" min={criteria.minJValue} max={criteria.maxJValue}
            onMin={(v) => update('minJValue', v)} onMax={(v) => update('maxJValue', v)} />
          <RangeField label="MACD柱" min={criteria.minMacdHist} max={criteria.maxMacdHist}
            onMin={(v) => update('minMacdHist', v)} onMax={(v) => update('maxMacdHist', v)} />
          <RangeField label="BOLL带宽" min={criteria.minBollWidth} max={criteria.maxBollWidth}
            onMin={(v) => update('minBollWidth', v)} onMax={(v) => update('maxBollWidth', v)} />
          <RangeField label="BOLL%B" min={criteria.minBollPercentB} max={criteria.maxBollPercentB}
            onMin={(v) => update('minBollPercentB', v)} onMax={(v) => update('maxBollPercentB', v)} />
        </Section>

        <Section title="信号与排列">
          <Field label="MACD信号">
            <Select value={criteria.macdCrossSignal ?? 'any'} onChange={(e) => update('macdCrossSignal', e.target.value)}>
              <option value="any">不限</option>
              <option value="golden_cross">金叉</option>
              <option value="death_cross">死叉</option>
              <option value="none">无交叉</option>
            </Select>
          </Field>
          <Field label="MACD信号天数">
            <Input type="number" value={criteria.macdCrossWithinDays ?? 0} onChange={(e) => update('macdCrossWithinDays', Number(e.target.value))} />
          </Field>
          <Field label="KDJ信号">
            <Select value={criteria.kdjCrossSignal ?? 'any'} onChange={(e) => update('kdjCrossSignal', e.target.value)}>
              <option value="any">不限</option>
              <option value="golden_cross">金叉</option>
              <option value="death_cross">死叉</option>
              <option value="none">无交叉</option>
            </Select>
          </Field>
          <Field label="KDJ信号天数">
            <Input type="number" value={criteria.kdjCrossWithinDays ?? 0} onChange={(e) => update('kdjCrossWithinDays', Number(e.target.value))} />
          </Field>
          <Field label="BOLL位置">
            <Select value={criteria.bollPosition ?? 'any'} onChange={(e) => update('bollPosition', e.target.value)}>
              <option value="any">不限</option>
              <option value="above_upper">上轨外</option>
              <option value="upper_zone">上轨区域</option>
              <option value="middle_upper">中轨上方</option>
              <option value="middle_lower">中轨下方</option>
              <option value="lower_zone">下轨区域</option>
              <option value="below_lower">下轨外</option>
            </Select>
          </Field>
        </Section>

        <Section title="均线排列">
          <div className="grid grid-cols-2 gap-2">
            <CheckField label="站上MA5" checked={!!criteria.priceAboveMa5} onChange={(v) => update('priceAboveMa5', v)} />
            <CheckField label="站上MA20" checked={!!criteria.priceAboveMa20} onChange={(v) => update('priceAboveMa20', v)} />
            <CheckField label="站上MA60" checked={!!criteria.priceAboveMa60} onChange={(v) => update('priceAboveMa60', v)} />
            <CheckField label="MA5>MA20" checked={!!criteria.ma5AboveMa20} onChange={(v) => update('ma5AboveMa20', v)} />
            <CheckField label="MA20>MA60" checked={!!criteria.ma20AboveMa60} onChange={(v) => update('ma20AboveMa60', v)} />
            <CheckField label="排除ST" checked={criteria.excludeSt ?? true} onChange={(v) => update('excludeSt', v)} />
          </div>
        </Section>
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

/** 分區標題組件（標題 + 內容區） */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-slate-400 border-b border-border pb-1">{title}</div>
      <div className="grid grid-cols-1 gap-3">{children}</div>
    </div>
  );
}

/** 範圍字段組件（最小值 + 最大值雙輸入框） */
function RangeField({ label, min, max, onMin, onMax }: {
  label: string;
  min: number | null | undefined;
  max: number | null | undefined;
  onMin: (v: number | null) => void;
  onMax: (v: number | null) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-muted">{label}</label>
      <div className="grid grid-cols-2 gap-2">
        <Input type="number" placeholder="最小" value={min ?? ''} onChange={(e) => onMin(e.target.value ? Number(e.target.value) : null)} />
        <Input type="number" placeholder="最大" value={max ?? ''} onChange={(e) => onMax(e.target.value ? Number(e.target.value) : null)} />
      </div>
    </div>
  );
}

/** 複選框字段組件（標籤 + checkbox） */
function CheckField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="accent-accent" />
      {label}
    </label>
  );
}
