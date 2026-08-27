/**
 * @file LogPanel 組件 — 運行日誌面板，以等寬字體顯示帶行號的日誌列表。
 */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

/**
 * LogPanel 組件 — 在卡片中展示日誌行列表，可選附帶狀態徽章。
 * @param logs 日誌行字符串數組
 * @param statusText 可選的狀態提示文字（顯示為徽章）
 */
export function LogPanel({ logs, statusText }: { logs: string[]; statusText?: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>运行日志</CardTitle>
        {statusText && <Badge variant="info">{statusText}</Badge>}
      </CardHeader>
      <CardContent>
        <div className="space-y-1 font-mono text-xs text-slate-400 max-h-48 overflow-auto">
          {logs.length === 0 ? (
            <div className="text-muted">暂无日志</div>
          ) : (
            logs.map((line, i) => (
              <div key={i} className="leading-relaxed">
                <span className="text-muted mr-2">[{String(i + 1).padStart(2, '0')}]</span>
                {line}
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
