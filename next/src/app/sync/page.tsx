/**
 * @file SyncPage 數據同步頁 — 提供 Baostock 數據同步的配置和操作界面，
 * 支持增量更新/日期範圍模式、復權類型選擇、指數/行業同步開關，
 * 實時展示同步任務狀態和進度。
 */
'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { api } from '@/lib/api';
import { Play, Square, RefreshCw } from 'lucide-react';
import { ErrorState } from '@/components/ui/ErrorState';
import type { SyncRequestDto } from '@/lib/api/types';

/** 今日日期（YYYY-MM-DD 格式） */
const today = new Date().toISOString().slice(0, 10);

/**
 * SyncPage 數據同步頁組件。
 * 通過 SWR 每 2 秒輪詢同步狀態，支持啟動/取消同步操作。
 */
export default function SyncPage() {
  const [request, setRequest] = useState<SyncRequestDto>({
    adjustflags: '1,2,3',
    startDate: '',
    endDate: today,
    codes: '',
    mode: 'incremental',
    syncIndex: true,
    syncIndustry: true,
  });
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const { data: status, mutate } = useSWR('/sync/status', () => api.syncStatus(), {
    refreshInterval: 2000,
  });

  const isRunning = status?.state === 'RUNNING';

  const run = async () => {
    setStarting(true);
    setError(null);
    try {
      await api.runSync(request);
      await mutate();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const cancel = async () => {
    setError(null);
    try {
      await api.cancelSync();
      await mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {error && <ErrorState message={`同步操作失敗: ${error}`} onRetry={() => setError(null)} />}

      <Card>
        <CardHeader>
          <CardTitle>數據同步（Baostock）</CardTitle>
          <Badge variant={isRunning ? 'warning' : status?.state === 'SUCCESS' ? 'success' : status?.state === 'FAILED' ? 'danger' : 'default'}>
            {status?.state ?? 'IDLE'}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 同步模式 */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted">同步模式</label>
            <Select
              value={request.mode ?? 'incremental'}
              onChange={(e) => setRequest({ ...request, mode: e.target.value })}
            >
              <option value="incremental">增量更新（只拉缺失數據，速度快）</option>
              <option value="range">指定日期範圍（全量拉取）</option>
            </Select>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {/* 復權類型 */}
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted">復權類型</label>
              <Select
                value={request.adjustflags ?? '3'}
                onChange={(e) => setRequest({ ...request, adjustflags: e.target.value })}
              >
                <option value="1,2,3">全部三種復權</option>
                <option value="1">後復權</option>
                <option value="2">前復權</option>
                <option value="3">不復權</option>
              </Select>
            </div>

            {/* 開始日期 */}
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted">
                開始日期{request.mode === 'incremental' ? '（增量模式可留空）' : ''}
              </label>
              <Input
                type="date"
                value={request.startDate ?? ''}
                onChange={(e) => setRequest({ ...request, startDate: e.target.value })}
                placeholder={request.mode === 'incremental' ? '自動' : '2021-01-01'}
              />
            </div>

            {/* 結束日期 */}
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted">結束日期</label>
              <Input
                type="date"
                value={request.endDate ?? today}
                onChange={(e) => setRequest({ ...request, endDate: e.target.value })}
              />
            </div>

            {/* 股票代碼 */}
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted">股票代碼（逗號分隔，留空全市場）</label>
              <Input
                value={request.codes ?? ''}
                onChange={(e) => setRequest({ ...request, codes: e.target.value })}
                placeholder="sh.600000,sz.000001"
              />
            </div>
          </div>

          {/* 指數同步開關 */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={request.syncIndex ?? false}
              onChange={(e) => setRequest({ ...request, syncIndex: e.target.checked })}
              className="w-4 h-4 rounded border-border accent-accent"
            />
            <span className="text-sm text-slate-200">同時同步滬深指數數據（8 個指數）</span>
          </label>

          {/* 行業同步開關 */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={request.syncIndustry ?? false}
              onChange={(e) => setRequest({ ...request, syncIndustry: e.target.checked })}
              className="w-4 h-4 rounded border-border accent-accent"
            />
            <span className="text-sm text-slate-200">同時同步行業分類數據（baostock 每週一更新）</span>
          </label>

          {/* 操作按鈕 */}
          <div className="flex gap-2">
            <Button onClick={run} disabled={isRunning || starting}>
              <Play className="w-4 h-4 mr-1" />
              啟動同步
            </Button>
            <Button variant="danger" onClick={cancel} disabled={!isRunning}>
              <Square className="w-4 h-4 mr-1" />
              取消
            </Button>
            <Button variant="outline" onClick={() => mutate()}>
              <RefreshCw className="w-4 h-4 mr-1" />
              刷新狀態
            </Button>
          </div>
        </CardContent>
      </Card>

      {status && (
        <Card>
          <CardHeader><CardTitle>任務狀態</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <Row label="狀態" value={status.state} />
              <Row label="進度" value={`${status.progress}%`} />
              <Row label="已寫入" value={`${status.written} 條`} />
              <Row label="消息" value={status.message} />
              <Row label="開始時間" value={status.startedAt ?? '-'} />
              <Row label="結束時間" value={status.finishedAt ?? '-'} />
              {status.error && <Row label="錯誤" value={status.error} />}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>使用說明</CardTitle></CardHeader>
        <CardContent className="text-sm text-slate-400 space-y-2">
          <p>1. 確保本機已安裝 Python 與 baostock、pymysql 包：<code className="text-accent">pip install baostock pymysql</code></p>
          <p>2. 後端通過 ProcessBuilder 編排 <code className="text-accent">ingestion/baostock_ingest.py</code> 拉取數據。</p>
          <p>3. <strong className="text-slate-200">增量更新模式</strong>：每隻股票只拉取資料庫中缺失的日期，速度快。</p>
          <p>4. <strong className="text-slate-200">日期範圍模式</strong>：拉取指定日期範圍的全部數據，適合補數據。</p>
          <p>5. 寫入採用 <code className="text-accent">ON DUPLICATE KEY UPDATE</code> 冪等策略，可重複運行。</p>
          <p>6. 全市場同步耗時較長，建議先用指定代碼測試。</p>
          <p>7. 也可直接在終端運行 <code className="text-accent">python ingestion/baostock_ingest.py</code> 進入交互式菜單。</p>
        </CardContent>
      </Card>
    </div>
  );
}

/** 單行鍵值展示組件（標籤 + 值） */
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-border-subtle py-1">
      <span className="text-muted">{label}</span>
      <span className="text-slate-200">{value}</span>
    </div>
  );
}
