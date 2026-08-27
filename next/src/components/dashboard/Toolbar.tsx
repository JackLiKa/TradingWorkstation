/**
 * @file Toolbar 組件 — 儀表盤搜索工具欄，包含股票搜索、復權選擇、日期範圍、條數等篩選條件，
 * 支持防抖自動搜索和手動搜索/重置。
 */
'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { StockSearchInput } from '@/components/dashboard/StockSearchInput';
import { Search, RotateCcw, Loader2 } from 'lucide-react';

/** 工具欄搜索條件值 */
export interface ToolbarValues {
  /** 股票代碼 */
  code: string;
  /** 復權類型（1=後復權, 2=前復權, 3=不復權） */
  adjustflag: number;
  /** 開始日期 */
  startDate: string;
  /** 結束日期 */
  endDate: string;
  /** 返回條數 */
  limit: number;
}

/** Toolbar 組件屬性 */
interface ToolbarProps {
  /** 默認搜索條件 */
  defaults: ToolbarValues;
  /** 外部傳入的搜索條件（如點擊波動列表股票時同步） */
  externalValues?: ToolbarValues | null;
  /** 搜索回調 */
  onSearch: (values: ToolbarValues) => void;
  /** 重置回調 */
  onReset: () => void;
  /** 是否啟用防抖自動搜索，默認 true */
  autoSearch?: boolean;
  /** 是否正在搜索（控制按鈕 loading 狀態） */
  searching?: boolean;
}

/**
 * Toolbar 組件 — 搜索工具欄，輸入停止 500ms 後自動觸發搜索。
 * @param defaults 默認條件
 * @param externalValues 外部同步的條件值
 * @param onSearch 搜索回調
 * @param onReset 重置回調
 * @param autoSearch 是否自動搜索
 * @param searching 是否搜索中
 */
export function Toolbar({ defaults, externalValues, onSearch, onReset, autoSearch = true, searching = false }: ToolbarProps) {
  const [values, setValues] = useState<ToolbarValues>(defaults);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 當外部值變化時同步（如點擊波動列表股票）
  useEffect(() => {
    if (externalValues) setValues(externalValues);
  }, [externalValues]);

  const update = <K extends keyof ToolbarValues>(key: K, value: ToolbarValues[K]) =>
    setValues((prev) => ({ ...prev, [key]: value }));

  // 防抖自動搜索：輸入停止 500ms 後自動觸發
  useEffect(() => {
    if (!autoSearch) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onSearch(values);
    }, 500);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [values, autoSearch, onSearch]);

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted">股票代码</label>
        <StockSearchInput
          value={values.code}
          onChange={(v) => update('code', v)}
          onSelect={(code) => {
            // 選中下拉建議後立即觸發搜索
            const newValues = { ...values, code };
            setValues(newValues);
            onSearch(newValues);
          }}
          className="w-48"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted">复权</label>
        <Select
          value={String(values.adjustflag)}
          onChange={(e) => update('adjustflag', Number(e.target.value))}
          className="w-28"
        >
          <option value="1">后复权</option>
          <option value="2">前复权</option>
          <option value="3">不复权</option>
        </Select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted">开始日期</label>
        <Input
          type="date"
          value={values.startDate}
          onChange={(e) => update('startDate', e.target.value)}
          className="w-40"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted">结束日期</label>
        <Input
          type="date"
          value={values.endDate}
          onChange={(e) => update('endDate', e.target.value)}
          className="w-40"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted">条数</label>
        <Input
          type="number"
          value={values.limit}
          onChange={(e) => update('limit', Number(e.target.value))}
          className="w-24"
        />
      </div>
      <Button onClick={() => onSearch(values)} disabled={searching}>
        {searching ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Search className="w-4 h-4 mr-1" />}
        搜索
      </Button>
      <Button variant="outline" onClick={onReset}>
        <RotateCcw className="w-4 h-4 mr-1" />
        重置
      </Button>
    </div>
  );
}
