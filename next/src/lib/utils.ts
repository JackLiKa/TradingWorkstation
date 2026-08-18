/**
 * @file 通用工具函數 — className 合併工具。
 */
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * 合併 Tailwind CSS 類名，自動處理衝突（後定義的覆蓋先定義的）。
 * @param inputs 任意數量的類名值（字符串、對象、數組等）
 * @returns 合併後的去重類名字符串
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
