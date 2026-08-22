/**
 * @file useEChartsOption — ECharts 共用封裝 hook。
 *
 * 統一處理 ECharts 圖表的常見關切點，避免每個圖表組件重複編寫：
 * - 主題色板（暗色/亮色，目前項目為暗色主題）
 * - tooltip 統一格式化（暗色背景、貨幣/百分比格式）
 * - 空態處理（無數據時返回「暫無數據」佔位 option）
 * - loading 狀態（外部傳入，hook 透明傳遞）
 *
 * 用法：
 * ```ts
 * const { option, loading, isEmpty } = useEChartsOption(rawData, (data) => ({
 *   xAxis: { type: 'category', data: data.map(d => d.date) },
 *   series: [{ type: 'line', data: data.map(d => d.value) }],
 * }));
 * ```
 */
'use client';

import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';

/** 暗色主題通用色板（與現有組件保持一致） */
export const DARK_THEME = {
  /** 軸線顏色 */
  axisLine: '#1e293b',
  /** 軸標籤顏色 */
  axisLabel: '#64748b',
  /** 分割線顏色 */
  splitLine: '#16213a',
  /** 標題文字顏色 */
  titleText: '#e2e8f0',
  /** 圖例文字顏色 */
  legendText: '#94a3b8',
  /** tooltip 背景 */
  tooltipBg: '#0f172a',
  /** tooltip 邊框 */
  tooltipBorder: '#1e293b',
  /** tooltip 文字 */
  tooltipText: '#e2e8f0',
  /** 背景透明 */
  transparent: 'transparent',
} as const;

/** 空態佔位 option — 顯示「暫無數據」 */
const EMPTY_OPTION: EChartsOption = {
  backgroundColor: DARK_THEME.transparent,
  animation: false,
  title: {
    text: '暫無數據',
    left: 'center',
    top: 'center',
    textStyle: {
      color: DARK_THEME.axisLabel,
      fontSize: 14,
      fontWeight: 'normal',
    },
  },
  xAxis: { show: false },
  yAxis: { show: false },
  series: [],
};

/** 暗色主題 tooltip 基礎配置（可被 builderFn 覆蓋） */
export const darkTooltipBase = {
  backgroundColor: DARK_THEME.tooltipBg,
  borderColor: DARK_THEME.tooltipBorder,
  textStyle: { color: DARK_THEME.tooltipText },
} as const;

/** 暗色主題 legend 基礎配置 */
export const darkLegendBase = {
  textStyle: { color: DARK_THEME.legendText },
} as const;

/**
 * 判斷原始數據是否為空（null / undefined / 空數組 / 空對象 / 空字符串）。
 * @param data 原始數據
 * @returns 是否為空
 */
export function isEmptyData(data: unknown): boolean {
  if (data == null) return true;
  if (typeof data === 'string') return data.length === 0;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === 'object') return Object.keys(data as object).length === 0;
  return false;
}

/** useEChartsOption 返回值 */
export interface UseEChartsOptionResult<TData> {
  /** 最終 ECharts option（空態時為佔位 option） */
  option: EChartsOption;
  /** loading 狀態（外部傳入，透明傳遞） */
  loading: boolean;
  /** 是否為空態（無數據） */
  isEmpty: boolean;
  /** 原始數據（透傳，方便調試） */
  data: TData | undefined;
}

/**
 * ECharts 共用封裝 hook。
 *
 * @param rawData 原始數據（可能為 undefined / 空數組）
 * @param builderFn 用戶提供的 option 構建函數 `(data) => EChartsOption`
 * @param loading 外部 loading 狀態（默認 false）
 * @returns `{ option, loading, isEmpty }`
 */
export function useEChartsOption<TData>(
  rawData: TData | undefined,
  builderFn: (data: TData) => EChartsOption,
  loading = false,
): UseEChartsOptionResult<TData> {
  const isEmpty = isEmptyData(rawData);

  const option = useMemo<EChartsOption>(() => {
    if (isEmpty || rawData == null) {
      return EMPTY_OPTION;
    }
    return builderFn(rawData);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawData, isEmpty]);

  return { option, loading, isEmpty, data: rawData };
}
