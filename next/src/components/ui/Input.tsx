/**
 * @file Input 輸入框組件 — 基於原生 input 的樣式封裝，
 * 使用 forwardRef 轉發 ref 以支持表單庫集成。
 */
import { InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

/** Input 組件屬性，直接擴展原生 input 屬性 */
export type InputProps = InputHTMLAttributes<HTMLInputElement>;

/**
 * Input 輸入框組件 — 統一暗色主題樣式的文本輸入框。
 * @param className 額外的 CSS 類名
 * @param props 其他原生 input 屬性
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'flex h-9 w-full rounded-md border border-border bg-bg-card px-3 py-1 text-sm text-slate-200 placeholder:text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent disabled:opacity-50',
        className
      )}
      {...props}
    />
  )
);
Input.displayName = 'Input';
