/**
 * @file AppProviders 全局 Provider 包裝器 — 配置 SWR 全局默認選項
 *（fetcher、不自動重新驗證、不自動重試、2 秒去重窗口）。
 */
'use client';

import { ReactNode } from 'react';
import { SWRConfig } from 'swr';
import { apiFetch } from '@/lib/api/client';

/**
 * AppProviders 組件 — 包裹整個應用，為所有 useSWR 調用提供全局配置。
 * @param children 子組件樹
 */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher: apiFetch,
        revalidateOnFocus: false,
        shouldRetryOnError: false,
        dedupingInterval: 2000,
      }}
    >
      {children}
    </SWRConfig>
  );
}
