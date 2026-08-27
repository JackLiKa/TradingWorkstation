/**
 * @file Select 下拉選擇框組件 — 基於原生 select 的樣式封裝，
 * 使用 forwardRef 轉發 ref 以支持表單庫集成。
 */
import { SelectHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

/** Select 組件屬性，直接擴展原生 select 屬性 */
export type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

/**
 * Select 下拉選擇框組件 — 統一暗色主題樣式的下拉選擇器。
 * @param className 額外的 CSS 類名
 * @param children option 子元素
 * @param props 其他原生 select 屬性
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        'flex h-9 w-full rounded-md border border-border bg-bg-card px-3 py-1 text-sm text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent disabled:opacity-50',
        className
      )}
      {...props}
    >
      {children}
    </select>
  )
);
Select.displayName = 'Select';
