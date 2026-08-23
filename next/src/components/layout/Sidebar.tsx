/**
 * @file Sidebar 側邊欄組件 — 應用主導航欄，桌面端固定左側，
 * 移動端通過漢堡按鈕展開抽屜式菜單。
 */
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, CandlestickChart, Database, Settings, SlidersHorizontal, Menu, X, Bot, Activity, Layers, Newspaper } from 'lucide-react';
import { cn } from '@/lib/utils';

/** 導航菜單項配置（路由 + 標籤 + 圖標） */
const NAV_ITEMS = [
  { href: '/', label: '总览面板', icon: LayoutDashboard },
  { href: '/industry', label: '行业分析', icon: Layers },
  { href: '/screener', label: '选股器与回测', icon: SlidersHorizontal },
  { href: '/agent', label: 'AI 策略优化', icon: Bot },
  { href: '/agent-dashboard', label: 'Agent Dashboard', icon: Activity },
  { href: '/news', label: '财经新闻', icon: Newspaper },
  { href: '/sync', label: '数据同步', icon: Database },
  { href: '/settings', label: '系统设置', icon: Settings },
];

/**
 * Sidebar 組件 — 根據當前路由高亮對應導航項，
 * 桌面端始終顯示，移動端通過狀態控制抽屜開關。
 * @returns 包含桌面側邊欄和移動端漢堡按鈕/抽屜的 JSX
 */
export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navContent = (
    <nav className="flex-1 p-2 space-y-1">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setMobileOpen(false)}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors',
              active
                ? 'bg-accent/10 text-accent'
                : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover'
            )}
          >
            <Icon className="w-4 h-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );

  const brand = (
    <div className="flex items-center gap-2 px-4 h-14 border-b border-border">
      <CandlestickChart className="w-5 h-5 text-accent" />
      <span className="font-semibold text-slate-100">量化工作台</span>
    </div>
  );

  return (
    <>
      {/* 桌面側邊欄 */}
      <aside className="hidden md:flex w-56 shrink-0 border-r border-border bg-bg-panel flex-col">
        {brand}
        {navContent}
        <div className="p-3 border-t border-border text-xs text-muted">
          Java 21 · Spring Boot · Next.js
        </div>
      </aside>

      {/* 手機頂部漢堡按鈕 */}
      <button
        className="md:hidden fixed top-3 left-3 z-50 p-2 rounded-md border border-border bg-bg-panel text-slate-200"
        onClick={() => setMobileOpen(true)}
        aria-label="打开菜单"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* 手機抽屜 */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="fixed inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="relative w-56 shrink-0 border-r border-border bg-bg-panel flex-col flex">
            <div className="flex items-center justify-between h-14 border-b border-border px-4">
              <div className="flex items-center gap-2">
                <CandlestickChart className="w-5 h-5 text-accent" />
                <span className="font-semibold text-slate-100">量化工作台</span>
              </div>
              <button onClick={() => setMobileOpen(false)} aria-label="关闭菜单">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            {navContent}
            <div className="p-3 border-t border-border text-xs text-muted">
              Java 21 · Spring Boot · Next.js
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
