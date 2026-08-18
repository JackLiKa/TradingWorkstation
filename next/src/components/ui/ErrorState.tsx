/**
 * @file ErrorState 錯誤狀態組件 — 用於在頁面中顯示錯誤信息，
 * 可選附帶「重試」按鈕觸發重新加載。
 */
'use client';

import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from './Button';

/** ErrorState 組件屬性 */
interface ErrorStateProps {
  /** 錯誤提示消息 */
  message: string;
  /** 重試回調，提供時顯示「重试」按鈕 */
  onRetry?: () => void;
}

/**
 * ErrorState 錯誤狀態組件 — 紅色邊框面板，顯示錯誤圖標和消息。
 * @param message 錯誤消息文本
 * @param onRetry 重試回調函數
 */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 flex items-center gap-3">
      <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
      <span className="text-sm text-red-300 flex-1">{message}</span>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="w-3.5 h-3.5 mr-1" />
          重试
        </Button>
      )}
    </div>
  );
}
