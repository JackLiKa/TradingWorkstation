/**
 * @file SettingsPage 系統設置頁 — 展示數據庫健康檢查結果，
 * 並提供數據庫連接配置表單（主機、端口、庫名、用戶、密碼、字符集）。
 */
'use client';

import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { api } from '@/lib/api';
import { Save, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { ErrorState } from '@/components/ui/ErrorState';
import type { DatabaseConfigUpdateDto } from '@/lib/api/types';

/**
 * SettingsPage 系統設置頁組件。
 * 通過 SWR 加載健康狀態和數據庫配置，支持保存配置到 .env 文件。
 */
export default function SettingsPage() {
  const { data: health, mutate: mutateHealth } = useSWR('/system/health', () => api.health(), { refreshInterval: 30000 });
  const { data: config } = useSWR('/system/database', () => api.databaseConfig());
  const [form, setForm] = useState<DatabaseConfigUpdateDto>({});
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (config) {
      setForm({ host: config.host, port: config.port, name: config.name, user: config.user, charset: config.charset, password: '' });
    }
  }, [config]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const update: DatabaseConfigUpdateDto = { ...form };
      if (!update.password) delete update.password;
      await api.updateDatabaseConfig(update);
      setSaved(true);
      setError('配置已校验。请手动修改 .env 文件中的 DB_* 键后重启后端生效。');
      setTimeout(() => setSaved(false), 5000);
      await mutateHealth();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {error && <ErrorState message={`保存失败: ${error}`} onRetry={() => setError(null)} />}

      <Card>
        <CardHeader>
          <CardTitle>数据库健康检查</CardTitle>
          <Button variant="outline" size="sm" onClick={() => mutateHealth()}>
            <RefreshCw className="w-3 h-3 mr-1" />
            重新检查
          </Button>
        </CardHeader>
        <CardContent>
          {health ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                {health.connected ? (
                  <CheckCircle2 className="w-5 h-5 text-down" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-up" />
                )}
                <span className="text-slate-200">{health.message}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <Row label="主机" value={health.host} />
                <Row label="端口" value={String(health.port)} />
                <Row label="数据库" value={health.databaseName} />
                <Row label="表结构" value={health.schemaValid ? '正常' : '异常'} />
              </div>
              {health.schemaIssues.length > 0 && (
                <div className="rounded-md border border-up/30 bg-up/5 p-3">
                  <div className="text-sm text-up font-medium mb-1">表结构问题：</div>
                  <ul className="text-xs text-slate-300 list-disc list-inside space-y-0.5">
                    {health.schemaIssues.map((issue, i) => <li key={i}>{issue}</li>)}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="text-muted">检查中...</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>数据库配置</CardTitle>
          {saved && <Badge variant="success">已保存，重启后端后生效</Badge>}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Field label="主机">
              <Input value={form.host ?? ''} onChange={(e) => setForm({ ...form, host: e.target.value })} />
            </Field>
            <Field label="端口">
              <Input type="number" value={form.port ?? ''} onChange={(e) => setForm({ ...form, port: Number(e.target.value) })} />
            </Field>
            <Field label="数据库名">
              <Input value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="用户名">
              <Input value={form.user ?? ''} onChange={(e) => setForm({ ...form, user: e.target.value })} />
            </Field>
            <Field label="密码">
              <Input type="password" value={form.password ?? ''} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="留空不修改" />
            </Field>
            <Field label="字符集">
              <Input value={form.charset ?? ''} onChange={(e) => setForm({ ...form, charset: e.target.value })} />
            </Field>
          </div>
          <div className="flex gap-2">
            <Button onClick={save} disabled={saving}>
              <Save className="w-4 h-4 mr-1" />
              保存到 .env
            </Button>
          </div>
          <p className="text-xs text-muted">
            配置写入仓库根目录 <code className="text-accent">.env</code>，重启后端服务后生效。密码不会回显，留空表示不修改。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

/** 單個表單字段組件（標籤 + 子元素） */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-muted">{label}</label>
      {children}
    </div>
  );
}

/** 單行鍵值展示組件（標籤 + 值） */
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border border-border rounded-md p-2 bg-bg-card">
      <span className="text-xs text-muted">{label}</span>
      <span className="text-slate-200 truncate">{value}</span>
    </div>
  );
}
