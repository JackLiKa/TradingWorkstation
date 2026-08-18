/**
 * @file AgentModelCard 模型狀態卡片 — 展示 LLM 模型可用性、提供商、免費標籤，
 * 支持點擊展開詳情、手動觸發檢查，帶動畫和視覺反饋。
 */
'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import type { AgentModelStatus } from '@/lib/api/types';
import {
  CheckCircle2, XCircle, RefreshCw, Loader2, Cpu, Zap, Gift,
  ChevronDown, ChevronUp, Clock, AlertTriangle, Sparkles
} from 'lucide-react';

/** AgentModelCard 組件屬性 */
interface Props {
  /** 模型狀態數據 */
  modelStatus: AgentModelStatus | undefined;
  /** 是否正在檢查模型 */
  checking: boolean;
  /** 手動觸發檢查的回調 */
  onCheck: () => void;
}

/**
 * AgentModelCard 組件 — 可展開的模型狀態卡片。
 * 摺疊狀態顯示模型徽章 + 檢查按鈕；展開後顯示詳細信息（提供商、模型名、最後檢查時間、錯誤信息）。
 * @param modelStatus 模型狀態數據
 * @param checking 是否正在檢查
 * @param onCheck 觸發檢查回調
 */
export function AgentModelCard({ modelStatus, checking, onCheck }: Props) {
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

  const available = modelStatus?.available ?? false;
  const isFree = modelStatus?.is_free ?? false;
  const provider = modelStatus?.provider ?? '未知';
  const modelName = modelStatus?.model_name ?? '未知';
  const lastCheck = modelStatus?.last_check ?? '';
  const error = modelStatus?.error;

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
      available
        ? 'border-green-500/30 bg-green-500/5'
        : 'border-red-500/30 bg-red-500/5'
    } ${pulseEffect ? 'ring-2 ring-accent/40' : ''}`}>
      {/* 頂部行：模型徽章 + 檢查按鈕 */}
      <div className="flex items-center justify-between gap-2 px-3 py-2.5">
        <div className="flex items-center gap-2 flex-wrap">
          {/* 狀態圖標 + 動畫 */}
          <div className={`flex items-center justify-center w-7 h-7 rounded-full ${
            available ? 'bg-green-500/15' : 'bg-red-500/15'
          } ${pulseEffect ? 'animate-pulse' : ''}`}>
            {checking ? (
              <Loader2 className="w-4 h-4 animate-spin text-accent" />
            ) : available ? (
              <CheckCircle2 className="w-4 h-4 text-green-400" />
            ) : (
              <XCircle className="w-4 h-4 text-red-400" />
            )}
          </div>

          {/* 提供商 + 模型名 */}
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <Cpu className="w-3 h-3 text-muted" />
              <span className="text-sm font-medium text-slate-200">{provider}</span>
              {available && isFree && (
                <span className="flex items-center gap-0.5 px-1.5 py-0 bg-green-500/20 rounded text-[10px] font-medium text-green-400">
                  <Gift className="w-2.5 h-2.5" />
                  免費
                </span>
              )}
              {!available && !checking && (
                <span className="flex items-center gap-0.5 px-1.5 py-0 bg-amber-500/20 rounded text-[10px] font-medium text-amber-400">
                  <AlertTriangle className="w-2.5 h-2.5" />
                  不可用
                </span>
              )}
            </div>
            <span className="text-xs text-muted">{modelName}</span>
          </div>
        </div>

        {/* 右側操作區 */}
        <div className="flex items-center gap-1.5">
          {/* 展開/收起按鈕 */}
          {modelStatus && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center justify-center w-7 h-7 rounded-md border border-border bg-bg-hover/50 hover:bg-bg-hover transition-colors text-muted hover:text-slate-200"
              title={expanded ? '收起詳情' : '展開詳情'}
            >
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}

          {/* 檢查模型按鈕 — 帶動畫和狀態反饋 */}
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
                檢查模型
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 展開的詳情面板 */}
      {expanded && modelStatus && (
        <div className="border-t border-border/50 px-3 py-3 space-y-2.5 animate-in fade-in slide-in-from-top-1 duration-200">
          {/* 狀態摘要 */}
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-accent" />
            <span className="text-xs font-medium text-slate-300">模型狀態詳情</span>
          </div>

          {/* 詳情網格 */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            {/* 提供商 */}
            <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5">
              <Cpu className="w-3 h-3 text-muted" />
              <span className="text-muted">提供商</span>
              <span className="ml-auto text-slate-200 font-medium">{provider}</span>
            </div>

            {/* 模型名 */}
            <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5">
              <Zap className="w-3 h-3 text-muted" />
              <span className="text-muted">模型</span>
              <span className="ml-auto text-slate-200 font-medium truncate max-w-[120px]">{modelName}</span>
            </div>

            {/* 可用性 */}
            <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5">
              {available ? <CheckCircle2 className="w-3 h-3 text-green-400" /> : <XCircle className="w-3 h-3 text-red-400" />}
              <span className="text-muted">可用性</span>
              <span className={`ml-auto font-medium ${available ? 'text-green-400' : 'text-red-400'}`}>
                {available ? '可用' : '不可用'}
              </span>
            </div>

            {/* 是否免費 */}
            <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5">
              <Gift className="w-3 h-3 text-muted" />
              <span className="text-muted">類型</span>
              <span className={`ml-auto font-medium ${isFree ? 'text-green-400' : 'text-amber-400'}`}>
                {isFree ? '免費' : '付費'}
              </span>
            </div>

            {/* 最後檢查時間 */}
            <div className="flex items-center gap-1.5 rounded-md bg-bg-hover/40 px-2 py-1.5 col-span-2">
              <Clock className="w-3 h-3 text-muted" />
              <span className="text-muted">最後檢查</span>
              <span className="ml-auto text-slate-200 font-medium">{formatTime(lastCheck)}</span>
            </div>
          </div>

          {/* 錯誤信息（有錯誤時顯示） */}
          {error && (
            <div className="flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/10 px-2.5 py-2">
              <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-medium text-red-400">錯誤信息</div>
                <div className="text-xs text-red-300/80 mt-0.5 break-all">{error}</div>
              </div>
            </div>
          )}

          {/* 提示信息 */}
          {!available && !error && (
            <div className="flex items-center gap-2 text-xs text-amber-400/80">
              <AlertTriangle className="w-3 h-3 flex-shrink-0" />
              點擊「檢查模型」重新驗證可用性，或檢查 agent/.env 中的 API Key 配置
            </div>
          )}
        </div>
      )}
    </div>
  );
}
