/**
 * @file RootLayout 根佈局 — Next.js App Router 的頂層佈局組件，
 * 配置全局 HTML 結構、暗色主題、側邊欄、頂部欄和加載遮罩。
 */
import type { Metadata } from 'next';
import './globals.css';
import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { DbStatusBanner } from '@/components/layout/DbStatusBanner';
import { LoadingOverlay } from '@/components/layout/LoadingOverlay';
import { AppProviders } from '@/components/layout/AppProviders';
import { FloatingChatCard } from '@/components/chat/FloatingChatCard';

/** 頁面元數據（標題和描述） */
export const metadata: Metadata = {
  title: '量化交易工作台',
  description: 'Java 21 + Spring Boot + Next.js 量化交易工作台',
  manifest: '/TradingWorkstation/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: '量化交易工作台',
  },
};

/** PWA Service Worker 注册脚本 */
const SW_SCRIPT = `
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/TradingWorkstation/sw.js')
        .catch((err) => console.log('SW registration failed:', err));
    });
  }
`;

/**
 * RootLayout 根佈局組件 — 包裹所有頁面的全局佈局。
 * 結構：Sidebar + (Topbar + main content) + LoadingOverlay，全部由 AppProviders 包裹。
 * @param children 頁面內容
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="dark">
      <body className="bg-bg text-slate-200 antialiased">
        <script dangerouslySetInnerHTML={{ __html: SW_SCRIPT }} />
        <AppProviders>
          <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex flex-1 flex-col min-w-0">
              <Topbar />
              <main className="flex-1 overflow-auto p-3 md:p-6">
                <div className="mb-4">
                  <DbStatusBanner />
                </div>
                {children}
              </main>
            </div>
          </div>
          <FloatingChatCard />
          <LoadingOverlay />
        </AppProviders>
      </body>
    </html>
  );
}
