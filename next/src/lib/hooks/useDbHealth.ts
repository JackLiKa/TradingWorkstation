/**
 * @file useDbHealth — 數據庫健康狀態全局 Hook，
 * 封裝 SWR 輪詢 /system/health，提供連接狀態、加載狀態和錯誤信息。
 * 多個組件共享同一份 SWR 緩存，避免重複請求。
 */
'use client';

import useSWR from 'swr';
import { api } from '@/lib/api';
import type { SystemHealthDto } from '@/lib/api/types';

/** 數據庫連接狀態枚舉 */
export type DbStatus = 'loading' | 'connected' | 'disconnected' | 'error';

/** useDbHealth 返回值 */
export interface DbHealthState {
  /** 當前連接狀態 */
  status: DbStatus;
  /** 健康檢查原始數據（loading/error 時為 undefined） */
  health: SystemHealthDto | undefined;
  /** 錯誤信息（status=error 時有值） */
  error: Error | undefined;
  /** 是否正在加載 */
  isLoading: boolean;
  /** 手動刷新 */
  refresh: () => Promise<unknown>;
}

/**
 * 數據庫健康狀態 Hook — 全局共享，15 秒輪詢。
 * 多個組件使用相同 key '/system/health'，SWR 自動去重。
 * @returns DbHealthState
 */
export function useDbHealth(): DbHealthState {
  const { data, error, isLoading, mutate } = useSWR<SystemHealthDto>(
    '/system/health',
    () => api.health(),
    { refreshInterval: 15000, revalidateOnFocus: true }
  );

  let status: DbStatus = 'loading';
  if (isLoading && !data) status = 'loading';
  else if (error) status = 'error';
  else if (data?.connected) status = 'connected';
  else if (data && !data.connected) status = 'disconnected';

  return {
    status,
    health: data,
    error: error as Error | undefined,
    isLoading,
    refresh: () => mutate(),
  };
}
