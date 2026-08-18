/**
 * @file Card 卡片組件系列 — 提供 Card / CardHeader / CardTitle / CardContent
 * 四個組件，用於構建統一風格的卡片佈局。
 */
import { HTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

/** Card 容器組件 — 圓角邊框面板，使用 forwardRef 轉發 ref */
export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('rounded-lg border border-border bg-bg-panel p-4', className)}
      {...props}
    />
  )
);
Card.displayName = 'Card';

/** CardHeader 頭部組件 — 卡片頂部區域，flex 佈局左右對齊 */
export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('mb-3 flex items-center justify-between', className)} {...props} />
  )
);
CardHeader.displayName = 'CardHeader';

/** CardTitle 標題組件 — 卡片標題，半粗體文字 */
export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn('text-base font-semibold text-slate-100', className)} {...props} />
  )
);
CardTitle.displayName = 'CardTitle';

/** CardContent 內容組件 — 卡片主體內容區域 */
export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('text-sm text-slate-300', className)} {...props} />
  )
);
CardContent.displayName = 'CardContent';
