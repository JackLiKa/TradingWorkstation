'use client';

import { useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';

interface ProgressIndicatorProps {
  active: boolean;
  label: string;
  /** 進度階段提示，按時間順序循環顯示 */
  stages?: string[];
}

/**
 * 運行進度指示器：
 * - 按鈕內旋轉圖標（由調用方在按鈕中渲染）
 * - 頁面頂部固定進度條（不確定動畫）
 * - 已用時間計時器
 * - 階段提示文字循環
 */
export function ProgressIndicator({ active, label, stages }: ProgressIndicatorProps) {
  const [elapsed, setElapsed] = useState(0);
  const [stageIndex, setStageIndex] = useState(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active) {
      setElapsed(0);
      setStageIndex(0);
      startRef.current = null;
      return;
    }
    startRef.current = Date.now();
    const timer = setInterval(() => {
      if (startRef.current) {
        setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
      }
    }, 200);
    return () => clearInterval(timer);
  }, [active]);

  useEffect(() => {
    if (!active || !stages || stages.length === 0) return;
    const stageTimer = setInterval(() => {
      setStageIndex((i) => (i + 1) % stages.length);
    }, 2000);
    return () => clearInterval(stageTimer);
  }, [active, stages]);

  if (!active) return null;

  const currentStage = stages && stages.length > 0 ? stages[stageIndex] : label;

  return (
    <div className="fixed top-0 left-0 right-0 z-[60] pointer-events-none">
      {/* 進度條動畫 */}
      <div className="h-1 bg-accent/20">
        <div className="h-full bg-accent animate-progress-indeterminate" />
      </div>
      {/* 狀態文字 */}
      <div className="flex items-center justify-center gap-2 py-1.5 bg-bg-panel/95 backdrop-blur-sm border-b border-border-subtle">
        <Loader2 className="w-4 h-4 text-accent animate-spin" />
        <span className="text-sm text-slate-200">{currentStage}</span>
        <span className="text-xs text-muted tabular-nums">
          已運行 {elapsed}s
        </span>
      </div>
      <style jsx>{`
        @keyframes progress-indeterminate {
          0% { width: 0%; margin-left: 0%; }
          50% { width: 40%; margin-left: 30%; }
          100% { width: 0%; margin-left: 100%; }
        }
        .animate-progress-indeterminate {
          animation: progress-indeterminate 1.5s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
