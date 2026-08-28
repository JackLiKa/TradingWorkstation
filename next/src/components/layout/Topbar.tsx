/**
 * @file Topbar 頂部欄組件 — 顯示應用標題。
 */
'use client';

/**
 * Topbar 組件 — 顯示應用標題的頂部欄。
 * @returns 頂部欄 JSX
 */
export function Topbar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-bg-panel px-3 md:px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-base md:text-lg font-semibold text-slate-100">量化交易工作台</h1>
      </div>
    </header>
  );
}
