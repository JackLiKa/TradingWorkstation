'use client';

import { useMemo, useState } from 'react';
import useSWR from 'swr';
import { api } from '@/lib/api';
import type { ProsperityAlertDto } from '@/lib/api/types';
import { ChartSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { RefreshCw, AlertTriangle, TrendingUp, TrendingDown, ArrowUpCircle, ArrowDownCircle, Bell, Mail } from 'lucide-react';
import { RefreshButton } from '@/components/ui/RefreshButton';
import { useDelayedRender } from '@/lib/hooks/useDelayedRender';
import { AnalysisTutorial } from '@/components/industry/AnalysisTutorial';

const THRESHOLD_OPTIONS = [5.0, 10.0, 15.0, 20.0];

const ALERT_TYPE_CONFIG: Record<string, { icon: typeof TrendingUp; color: string; bg: string }> = {
  surge: { icon: TrendingUp, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
  plunge: { icon: TrendingDown, color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
  grade_up: { icon: ArrowUpCircle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
  grade_down: { icon: ArrowDownCircle, color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
};

const SEVERITY_CONFIG: Record<string, { label: string; color: string }> = {
  high: { label: '高', color: 'text-red-400 bg-red-500/15' },
  medium: { label: '中', color: 'text-amber-400 bg-amber-500/15' },
  low: { label: '低', color: 'text-slate-400 bg-slate-500/15' },
};

export function ProsperityAlertsPanel() {
  const [threshold, setThreshold] = useState(10.0);
  const [notifySending, setNotifySending] = useState(false);
  const [notifyResult, setNotifyResult] = useState<string | null>(null);

  const key = `/stock/industry-prosperity/alerts?threshold=${threshold}`;
  const { data, error, isLoading, mutate, isValidating } = useSWR<ProsperityAlertDto>(
    key,
    () => api.prosperityAlerts(threshold),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  );
  const canRender = useDelayedRender(isLoading);

  const handleSendNotification = async () => {
    setNotifySending(true);
    setNotifyResult(null);
    try {
      const result = await api.prosperityAlerts(threshold, true);
      setNotifyResult(`已觸發通知（${result.alerts.length} 條預警），郵件/Webhook 將異步發送。`);
    } catch (e) {
      setNotifyResult(`通知發送失敗：${String(e)}`);
    } finally {
      setNotifySending(false);
      setTimeout(() => setNotifyResult(null), 5000);
    }
  };

  const stats = useMemo(() => {
    if (!data || !data.alerts) return null;
    const high = data.alerts.filter((a) => a.severity === 'high').length;
    const medium = data.alerts.filter((a) => a.severity === 'medium').length;
    const surges = data.alerts.filter((a) => a.alertType === 'surge' || a.alertType === 'grade_up').length;
    const plunges = data.alerts.filter((a) => a.alertType === 'plunge' || a.alertType === 'grade_down').length;
    return { high, medium, surges, plunges, total: data.alerts.length };
  }, [data]);

  return (
    <div className="space-y-3">
      <AnalysisTutorial tutorialKey="prosperityAlerts" />
      {/* 參數選擇器 */}
      <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-bg-panel p-3">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">突變閾值：</span>
          {THRESHOLD_OPTIONS.map((t) => (
            <button
              key={t}
              onClick={() => setThreshold(t)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                threshold === t ? 'bg-accent/10 text-accent' : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
              }`}
            >
              {t.toFixed(0)}
            </button>
          ))}
        </div>
        <RefreshButton
          onClick={() => mutate()}
          isLoading={isValidating}
          className="ml-auto"
        />
        {data && data.alerts.length > 0 && (
          <button
            onClick={handleSendNotification}
            disabled={notifySending}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-accent/10 text-accent hover:bg-accent/20 disabled:opacity-50"
          >
            {notifySending ? (
              <RefreshCw className="w-3 h-3 animate-spin" />
            ) : (
              <Bell className="w-3 h-3" />
            )}
            發送通知
          </button>
        )}
      </div>

      {/* 通知結果提示 */}
      {notifyResult && (
        <div className="rounded-md border border-accent/30 bg-accent/5 p-2 text-xs text-accent flex items-center gap-2">
          <Mail className="w-3 h-3" />
          {notifyResult}
        </div>
      )}

      {/* 統計摘要 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <p className="text-xs text-muted">預警總數</p>
            </div>
            <p className="text-lg font-semibold text-slate-100">{stats.total}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <p className="text-xs text-muted">高嚴重度</p>
            </div>
            <p className="text-lg font-semibold text-red-400">{stats.high}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-4 h-4 text-red-400" />
              <p className="text-xs text-muted">上升預警</p>
            </div>
            <p className="text-lg font-semibold text-red-400">{stats.surges}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-panel p-3">
            <div className="flex items-center gap-2 mb-1">
              <TrendingDown className="w-4 h-4 text-green-400" />
              <p className="text-xs text-muted">下降預警</p>
            </div>
            <p className="text-lg font-semibold text-green-400">{stats.plunges}</p>
          </div>
        </div>
      )}

      {/* 摘要文字 */}
      {data && (
        <div className="rounded-md border border-border bg-bg-panel p-3 text-sm text-slate-300">
          {data.summary}
        </div>
      )}

      {(isLoading || !canRender) && <ChartSkeleton />}
      {error && <ErrorState message={String(error)} onRetry={() => mutate()} />}

      {/* 預警列表 */}
      {!isLoading && !error && canRender && data && data.alerts.length > 0 && (
        <div className="space-y-2">
          {data.alerts.map((alert, i) => {
            const config = ALERT_TYPE_CONFIG[alert.alertType] || ALERT_TYPE_CONFIG.surge;
            const sevConfig = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.low;
            const Icon = config.icon;

            return (
              <div
                key={i}
                className={`rounded-lg border p-3 ${config.bg}`}
              >
                <div className="flex items-start gap-3">
                  <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${config.color}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-semibold text-slate-100 truncate">
                        {alert.industry}
                      </span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${sevConfig.color}`}>
                        {sevConfig.label}
                      </span>
                      <span className="text-xs text-muted">{alert.alertTypeName}</span>
                    </div>
                    <p className="text-xs text-slate-300 mb-1">{alert.message}</p>
                    <div className="flex items-center gap-3 text-xs text-muted">
                      <span>
                        景氣度：{alert.yesterdayProsperity.toFixed(1)} → {alert.todayProsperity.toFixed(1)}
                      </span>
                      <span className={alert.change >= 0 ? 'text-red-400' : 'text-green-400'}>
                        {alert.change >= 0 ? '+' : ''}{alert.change.toFixed(1)}
                      </span>
                      <span>
                        等級：{alert.yesterdayGrade} → {alert.todayGrade}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 無預警 */}
      {!isLoading && !error && canRender && data && data.alerts.length === 0 && (
        <div className="rounded-lg border border-border bg-bg-panel p-8 text-center">
          <p className="text-sm text-muted mb-2">本期無景氣度異常預警</p>
          <p className="text-xs text-muted">
            所有行業景氣度變化均在閾值 {threshold.toFixed(0)} 以內，未檢測到等級躍遷。
          </p>
        </div>
      )}

      <p className="text-xs text-muted">
        預警規則：景氣度變化絕對值 ≥ 閾值時觸發突升/突降預警；等級跨級變化時觸發等級躍遷預警。
        高嚴重度 = 變化 ≥ 2×閾值 或 等級跳躍 ≥ 2 級。
      </p>
    </div>
  );
}
