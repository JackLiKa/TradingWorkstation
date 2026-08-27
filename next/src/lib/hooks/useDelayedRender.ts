/**
 * useDelayedRender — 延時渲染 hook，避免數據還沒拿到就渲染完。
 *
 * 當 isLoading 從 true 變為 false 時，額外等待 delayMs 再允許渲染。
 * 這樣可以確保數據完全到位後再渲染圖表，避免 ECharts 用空數據渲染後又閃爍更新。
 *
 * @param isLoading 是否正在載入
 * @param delayMs 延時毫秒數，默認 300ms
 * @returns 是否可以渲染
 */
'use client';

import { useState, useEffect } from 'react';

export function useDelayedRender(isLoading: boolean, delayMs = 300): boolean {
  const [canRender, setCanRender] = useState(false);

  useEffect(() => {
    if (isLoading) {
      setCanRender(false);
      return;
    }
    // isLoading 為 false 時，延時一小段再允許渲染
    const timer = setTimeout(() => {
      setCanRender(true);
    }, delayMs);
    return () => clearTimeout(timer);
  }, [isLoading, delayMs]);

  return canRender;
}
