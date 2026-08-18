/**
 * @file 全局加載狀態管理 — 使用 Zustand 管理全屏 Loading Overlay 的顯示/隱藏。
 */
import { create } from 'zustand';

/** 加載狀態接口 */
interface LoadingState {
  /** 是否正在加載 */
  loading: boolean;
  /** 加載提示消息 */
  message: string;
  /** 開始加載
   * @param message 加載提示消息，默認 "加载中..."
   */
  start: (message?: string) => void;
  /** 停止加載 */
  stop: () => void;
}

export const useLoadingStore = create<LoadingState>((set) => ({
  loading: false,
  message: '',
  start: (message = '加载中...') => set({ loading: true, message }),
  stop: () => set({ loading: false, message: '' }),
}));
