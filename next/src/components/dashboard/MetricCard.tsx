/**
 * @file MetricCard 組件 — 儀表盤指標卡片，展示單個指標的標題、值和副標題。
 */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import type { DashboardMetricDto } from '@/lib/api/types';

/**
 * MetricCard 組件 — 單個指標卡片。
 * @param metric 指標數據（標題 + 值 + 副標題）
 */
export function MetricCard({ metric }: { metric: DashboardMetricDto }) {
  return (
    <Card className="flex flex-col gap-1">
      <CardHeader className="mb-0">
        <CardTitle className="text-sm text-muted">{metric.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-slate-100 tabular-nums">{metric.value}</div>
        <div className="text-xs text-muted mt-1">{metric.subtitle}</div>
      </CardContent>
    </Card>
  );
}

/**
 * MetricGrid 組件 — 指標卡片網格佈局，響應式排列多個 MetricCard。
 * @param metrics 指標數據數組
 */
export function MetricGrid({ metrics }: { metrics: DashboardMetricDto[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
      {metrics.map((m) => (
        <MetricCard key={m.title} metric={m} />
      ))}
    </div>
  );
}
