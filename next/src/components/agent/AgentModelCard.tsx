/**
 * @file AgentModelCard 模型狀態卡片 — 展示全部 LLM 模型可用性（Qoder + Devin），
 * 每個模型獨立顯示狀態，支持點擊展開詳情、手動觸發檢查全部模型。
 */
'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import type { AgentModelStatus, ModelCheckResult } from '@/lib/api/types';
import {
  CheckCircle2, XCircle, RefreshCw, Loader2, Cpu, Zap, Gift,
  ChevronDown, ChevronUp, Clock, AlertTriangle, Sparkles
} from 'lucide-react';

/** AgentModelCard 組件屬性 */
interface Props {
  /** 當前選中的模型狀態（向後兼容） */
  modelStatus: AgentModelStatus | undefined;
  /** 全部模型檢查結果列表 */
  allModels?: ModelCheckResult[];
  /** 是否正在檢查模型 */
  checking: boolean;
  /** 手動觸發檢查的回調 */
  onCheck: () => void;
}

/** 供應商顯示名稱 */
const PROVIDER_LABELS: Record<string, string> = {
  qoder: 'Qoder Lite',
  devin: 'Devin GLM-5.2',
  none: '不可用',
  unknown: '未知',
};

/**
 * AgentModelCard 組件 — 顯示全部模型狀態。
 * 摺疊狀態顯示每個供應商的徽章 + 檢查按鈕；展開後顯示詳細信息。
 */
export function AgentModelCard({ modelStatus, allModels, checking, onCheck }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [pulseEffect, setPulseEffect] = useState(false);

  // 模型狀態變化時觸發脈動效果
  useEffect(() => {
    if (modelStatus) {
      setPulseEffect(true);
      const timer = setTimeout(() => setPulseEffect(false), 600);
      return () => clearTimeout(timer);
    }
  }, [modelStatus?.available, modelStatus?.last_check]);

  // 使用 allModels 或退化到單個 modelStatus
  const models: ModelCheckResult[] = allModels && allModels.length > 0
    ? allModels
    : modelStatus
      ? [{
          provider: modelStatus.provider,
          model_name: modelStatus.model_name,
          available: modelStatus.available,
          is_free: modelStatus.is_free,
          last_check: modelStatus.last_check,
          error: modelStatus.error ?? '',
        }]
      : [];

  const anyAvailable = models.some((m) => m.available);
  const availableCount = models.filter((m) => m.available).length;

  // 格式化時間
  const formatTime = (iso: string) => {
    if (!iso) return '尚未檢查';
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  };

  return (
    <div className={`rounded-lg border transition-all duration-300 ${
      anyAvailable
        ? 'border-green-500/30 bg-green-500/5'
        : 'border-red-500/30 bg-red-500/5'
    } ${pulseEffect ? 'ring-2 ring-accent/40' : ''}`}>
      {/* 頂部行：模型徽章 + 檢查按鈕 */}
      <div className="flex items-center justify-between gap-2 px-3 py-2.5">
        <div className="flex items-center gap-2 flex-wrap">
          {/* 狀態圖標 + 動畫 */}
          <div className={`flex items-center justify-center w-7 h-7 rounded-full ${
            anyAvailable ? 'bg-green-500/15' : 'bg-red-500/15'
          } ${pulseEffect ? 'animate-pulse' : ''}`}>
            {checking ? (
              <Loader2 className="w-4 h-4 animate-spin text-accent" />
            ) : anyAvailable ? (
              <CheckCircle2 className="w-4 h-4 text-green-400" />
            ) : (
              <XCircle className="w-4 h-4 text-red-400" />
            )}
          </div>

          {/* 全部模型徽章列表 */}
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5 flex-wrap">
              <Cpu className="w-3 h-3 text-muted" />
              <span className="text-sm font-medium text-slate-200">
                全部模型 ({availableCount}/{models.length})
              </span>
              {anyAvailable && (
                <span className="flex items-center gap-0.5 px-1.5 py-0 bg-green-500/20 rounded text-[10px] font-medium text-green-400">
                  <Gift className="w-2.5 h-2.5" />
                  免費
                </span>
              )}
              {!anyAvailable && !checking && (
                <span className="flex items-center gap-0.5 px-1.5 py-0 bg-amber-500/20 rounded text-[10px] font-medium text-amber-400">
                  <AlertTriangle className="w-2.5 h-2.5" />
                  全部不可用
                </span>
              )}
            </div>
            {/* 每個供應商的獨立徽章 */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {models.map((m) => (
                <span
                  key={m.provider}
                  className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                    m.available
                      ? 'bg-green-500/15 text-green-400'
                      : 'bg-red-500/15 text-red-400'
                  }`}
                >
                  {m.available ? (
                    <CheckCircle2 className="w-2.5 h-2.5" />
                  ) : (
                    <XCircle className="w-2.5 h-2.5" />
                  )}
                  {PROVIDER_LABELS[m.provider] ?? m.provider}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* 右側操作區 */}
        <div className="flex items-center gap-1.5">
          {/* 展開/收起按鈕 */}
          {models.length > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center justify-center w-7 h-7 rounded-md border border-border bg-bg-hover/50 hover:bg-bg-hover transition-colors text-muted hover:text-slate-200"
              title={expanded ? '收起詳情' : '展開詳情'}
            >
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}

          {/* 檢查全部模型按鈕 */}
          <Button
            variant="outline"
            size="sm"
            onClick={onCheck}
            disabled={checking}
            className={`transition-all ${checking ? 'scale-95' : 'hover:scale-105'}`}
          >
            {checking ? (
              <>
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                檢查中...
              </>
            ) : (
              <>
                <RefreshCw className="w-3 h-3 mr-1 group-hover:rotate-180 transition-transform" />
                檢查全部模型
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 展開的詳情面板 — 每個模型獨立顯示 */}
      {expanded && models.length > 0 && (
        <div className="border-t border-border/50 px-3 py-3 space-y-3 animate-in fade-in slide-in-from-top-1 duration-200">
          {/* 狀態摘要 */}
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-accent" />
            <span className="text-xs font-medium text-slate-300">
              全部模型狀態詳情（{availableCount}/{models.length} 可用）
            </span>
          </div>

          {/* 每個模型一個詳情卡片 */}
          {models.map((m) => (
            <ModelDetailCard key={m.provider} model={m} formatTime={formatTime} />
          ))}

          {/* 全部不可用時的提示 */}
          {!anyAvailable && (
            <div className="flex items-center gap-2 text-xs text-amber-400/80">
              <AlertTriangle className="w-3 h-3 flex-shrink-0" />
              點擊「檢查全部模型」重新驗證可用性，或檢查 agent/.env 中的 API Key 配置
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** 單個模型詳情卡片 */
function ModelDetailCard({ model, formatTime }: { model: ModelCheckResult; formatTime: (iso: string) => string }) {
  const available = model.available;
  const isFree = model.is_free;
  const provider = PROVIDER_LABELS[model.provider] ?? model.provider;
  const modelName = model.model_name;

  return (
    <div className={`rounded-md border p-2.5 space-y-2 ${
      available ? 'border-green-500/20 bg-green-500/5' : 'border-red-500/20 bg-red-500/5'
    }`}>
      {/* 模型標題 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {available ? <CheckCircle2 className="w-3.5 h-3.5 text-green-400" /> : <XCircle className="w-3.5 h-3.5 text-red-400" />}
          <span className="text-sm font-medium text-slate-200">{provider}</span>
          <Badge variant={available ? 'success' : 'danger'}>
            {available ? '可用' : '不可用'}
          </Badge>
          {isFree && available && (
            <span className="flex items-center gap-0.5 px-1.5 py-0 bg-green-500/20 rounded text-[10px] font-medium text-green-400">
              <Gift className="w-2.5 h-2.5" />
              免費
            </span>
          )}
        </div>
      </div>

      {/* 詳情網格 */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5">
          <Cpu className="w-3 h-3 text-muted" />
          <span className="text-muted">提供商</span>
          <span className="ml-auto text-slate-200 font-medium">{provider}</span>
        </div>
        <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5">
          <Zap className="w-3 h-3 text-muted" />
          <span className="text-muted">模型</span>
          <span className="ml-auto text-slate-200 font-medium truncate max-w-[120px]">{modelName}</span>
        </div>
        <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5">
          {available ? <CheckCircle2 className="w-3 h-3 text-green-400" /> : <XCircle className="w-3 h-3 text-red-400" />}
          <span className="text-muted">可用性</span>
          <span className={`ml-auto font-medium ${available ? 'text-green-400' : 'text-red-400'}`}>
            {available ? '可用' : '不可用'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5">
          <Gift className="w-3 h-3 text-muted" />
          <span className="text-muted">類型</span>
          <span className={`ml-auto font-medium ${isFree ? 'text-green-400' : 'text-amber-400'}`}>
            {isFree ? '免費' : '付費'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5 col-span-2">
          <Clock className="w-3 h-3 text-muted" />
          <span className="text-muted">最後檢查</span>
          <span className="ml-auto text-slate-200 font-medium">{formatTime(model.last_check)}</span>
        </div>
      </div>

      {/* 錯誤信息 */}
      {model.error && (
        <div className="flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/10 px-2.5 py-2">
          <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <div className="text-xs font-medium text-red-400">錯誤信息</div>
            <div className="text-xs text-red-300/80 mt-0.5 break-all">{model.error}</div>
          </div>
        </div>
      )}
    </div>
  );
}
