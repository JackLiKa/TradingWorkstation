/**
 * @file Button 按鈕組件 — 基於 class-variance-authority 的多變體按鈕，
 * 支持 5 種樣式變體和 4 種尺寸。
 */
import { ButtonHTMLAttributes, forwardRef } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

/** 按鈕樣式定義（基礎類名 + 變體 + 尺寸） */
const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        default: 'bg-accent text-white hover:bg-accent-muted',
        secondary: 'bg-bg-hover text-slate-200 hover:bg-slate-700',
        outline: 'border border-border bg-transparent hover:bg-bg-hover text-slate-200',
        ghost: 'hover:bg-bg-hover text-slate-200',
        danger: 'bg-up text-white hover:bg-red-600',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-10 px-6',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  }
);

/** Button 組件屬性，擴展原生 button 屬性並增加 variant/size 選項 */
export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

/**
 * Button 按鈕組件 — 使用 forwardRef 轉發 ref，支持多種樣式變體和尺寸。
 * @param className 額外的 CSS 類名
 * @param variant 樣式變體（default/secondary/outline/ghost/danger）
 * @param size 尺寸（default/sm/lg/icon）
 * @param props 其他原生 button 屬性
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  )
);
Button.displayName = 'Button';
