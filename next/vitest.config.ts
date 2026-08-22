/**
 * @file Vitest 配置 — 前端單元測試。
 *
 * 使用 jsdom 環境以支持 React 組件 / DOM API 測試，
 * 路徑別名 @/* 映射到 src/*（與 tsconfig.json 保持一致）。
 */
import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
    },
  },
});
