/**
 * @file 格式化工具函數 — 用於將數值格式化為展示用的字符串
 *（百分比、貨幣、成交量、交叉信號描述等）。
 */

/**
 * 格式化百分比數值。
 * @param value 數值（如 3.14 表示 3.14%）
 * @param digits 保留小數位數，默認 2
 * @returns 格式化後的字符串（如 "3.14%"），null 時返回 "0.00%"
 */
export function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value == null) return '0.00%';
  return `${value.toFixed(digits)}%`;
}

/**
 * 格式化貨幣金額（自動轉換為「億」或「萬」單位）。
 * @param value 金額數值
 * @returns 格式化後的字符串（如 "1.23 億"、"5.00 萬"）
 */
export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return '0';
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)} 亿`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(2)} 万`;
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * 格式化成交量（自動轉換為「億」或「萬」單位）。
 * @param value 成交量數值
 * @returns 格式化後的字符串，null 時返回 "-"
 */
export function formatVolume(value: number | null | undefined): string {
  if (value == null) return '-';
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}亿`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(2)}万`;
  return String(value);
}

/**
 * 格式化數值為固定位數的字符串。
 * @param value 數值
 * @param digits 保留小數位數，默認 2
 * @returns 格式化後的字符串，null 時返回 "-"
 */
export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value == null) return '-';
  return value.toFixed(digits);
}

/**
 * 根據漲跌幅返回對應的 Tailwind CSS 顏色類名。
 * @param value 漲跌幅數值
 * @returns 正數返回 'text-up'（紅色），負數返回 'text-down'（綠色），0 或 null 返回灰色
 */
export function pctClass(value: number | null | undefined): string {
  if (value == null || value === 0) return 'text-slate-300';
  return value > 0 ? 'text-up' : 'text-down';
}

/**
 * 將交叉信號枚舉值轉換為中文描述。
 * @param signal 信號枚舉（golden_cross / death_cross / none / 其他）
 * @returns 中文描述（金叉 / 死叉 / 无交叉 / 不限）
 */
export function describeCross(signal: string): string {
  switch (signal) {
    case 'golden_cross': return '金叉';
    case 'death_cross': return '死叉';
    case 'none': return '无交叉';
    default: return '不限';
  }
}

/**
 * 將布林帶位置枚舉值轉換為中文描述。
 * @param position 位置枚舉（above_upper / upper_zone / middle_upper 等）
 * @returns 中文描述（上轨外 / 上轨区域 / 中轨上方 等）
 */
export function describeBoll(position: string): string {
  switch (position) {
    case 'above_upper': return '上轨外';
    case 'upper_zone': return '上轨区域';
    case 'middle_upper': return '中轨上方';
    case 'middle_lower': return '中轨下方';
    case 'lower_zone': return '下轨区域';
    case 'below_lower': return '下轨外';
    default: return '不限';
  }
}
