/**
 * @file Badge 徽章組件 — 用於顯示狀態標籤（成功/警告/危險/信息/默認）。
 */
import { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

/** Badge 組件屬性，擴展原生 span 屬性並增加 variant 選項 */
interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  /** 徽章樣式變體 */
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
}

/** 各變體對應的 Tailwind CSS 類名 */
const variants: Record<string, string> = {
  default: 'bg-bg-hover text-slate-300 border-border',
  success: 'bg-down/10 text-down border-down/30',
  warning: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  danger: 'bg-up/10 text-up border-up/30',
  info: 'bg-accent/10 text-accent border-accent/30',
};

/**
 * Badge 徽章組件 — 行內標籤，用於顯示狀態或分類信息。
 * @param className 額外的 CSS 類名
 * @param variant 樣式變體，默認 'default'
 * @param props 其他原生 span 屬性
 */
export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
