/**
 * 骨架屏组件 — 数据加载时显示占位动画，避免空白页面。
 */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-bg-hover/60 ${className}`} />;
}

export function MetricCardSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-bg-panel p-4 space-y-2">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-6 w-28" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

export function MetricGridSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <MetricCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 8, cols = 10 }: { rows?: number; cols?: number }) {
  return (
    <div className="rounded-lg border border-border bg-bg-panel overflow-hidden">
      <div className="p-4 border-b border-border">
        <Skeleton className="h-5 w-24" />
      </div>
      <div className="p-3 space-y-2">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex gap-2">
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton key={c} className="h-4 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-bg-panel p-4 space-y-3">
      <Skeleton className="h-5 w-32" />
      <Skeleton className="h-[300px] w-full" />
    </div>
  );
}

export function MoversSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="rounded-lg border border-border bg-bg-panel p-4 space-y-2">
      <Skeleton className="h-5 w-20" />
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center justify-between py-1">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}
