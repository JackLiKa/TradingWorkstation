/**
 * @file AnalysisGuidePage 進階分析方法教學頁 —
 * 左側導航列出 13 個進階分析方法，右側顯示選中方法的完整教學內容。
 * 響應式：手機上導航變為頂部下拉選單。
 */
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, BookOpen, AlertTriangle, FlaskConical, Lightbulb } from 'lucide-react';
import { ANALYSIS_TUTORIALS, ANALYSIS_TUTORIAL_KEYS } from '@/lib/analysis-tutorials';

/** 導航項：key + 中文標題 */
const NAV_ITEMS = ANALYSIS_TUTORIAL_KEYS.map((key) => ({
  key,
  title: ANALYSIS_TUTORIALS[key].title,
}));

export default function AnalysisGuidePage() {
  const [selected, setSelected] = useState<string>(NAV_ITEMS[0].key);
  const tutorial = ANALYSIS_TUTORIALS[selected];

  return (
    <div className="space-y-4 p-4 md:p-6 max-w-7xl mx-auto">
      {/* 頁面標題 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">進階分析方法教學</h1>
          <p className="text-sm text-muted mt-1">
            13 個進階分析視圖的原理、指標含義、方法論限制與科學性評估
          </p>
        </div>
        <Link
          href="/industry"
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-accent transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          返回行業分析
        </Link>
      </div>

      {/* 主體：左側導航 + 右側內容 */}
      <div className="flex flex-col lg:flex-row gap-4">
        {/* 桌面端左側導航 */}
        <nav className="hidden lg:block w-56 flex-shrink-0">
          <ul className="space-y-1 sticky top-4">
            {NAV_ITEMS.map((item, idx) => {
              const active = selected === item.key;
              return (
                <li key={item.key}>
                  <button
                    onClick={() => setSelected(item.key)}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors ${
                      active
                        ? 'bg-accent/15 text-accent border border-accent/30'
                        : 'text-slate-400 hover:text-slate-100 hover:bg-bg-hover border border-transparent'
                    }`}
                  >
                    <span className="text-xs text-muted flex-shrink-0">{idx + 1}.</span>
                    <span className="truncate">{item.title}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* 手機端頂部下拉選單 */}
        <div className="lg:hidden">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full bg-bg-panel text-sm text-slate-100 rounded-md border border-border px-3 py-2 outline-none"
          >
            {NAV_ITEMS.map((item, idx) => (
              <option key={item.key} value={item.key}>
                {idx + 1}. {item.title}
              </option>
            ))}
          </select>
        </div>

        {/* 右側內容 */}
        <div className="flex-1 min-w-0">
          {tutorial && (
            <div className="rounded-lg border border-border bg-bg-panel p-5 md:p-6 space-y-5">
              {/* 標題 */}
              <div className="flex items-center gap-2 pb-3 border-b border-border">
                <BookOpen className="w-5 h-5 text-accent" />
                <h2 className="text-lg font-semibold text-slate-100">{tutorial.title}</h2>
              </div>

              {/* 原理 */}
              <section>
                <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-300 mb-2">
                  <Lightbulb className="w-4 h-4 text-yellow-400" />
                  原理
                </h3>
                <p className="text-sm text-slate-300 leading-relaxed">{tutorial.principle}</p>
              </section>

              {/* 指標含義 */}
              <section>
                <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-300 mb-3">
                  <BookOpen className="w-4 h-4 text-accent" />
                  指標含義與解讀
                </h3>
                <ul className="space-y-3">
                  {tutorial.indicators.map((ind, i) => (
                    <li key={i} className="rounded-md bg-slate-800/50 border border-border/60 p-3">
                      <p className="font-medium text-slate-100">{ind.name}</p>
                      <p className="text-sm text-slate-400 mt-1.5">
                        <span className="text-slate-500">含義：</span>
                        {ind.meaning}
                      </p>
                      <p className="text-sm text-slate-400 mt-1">
                        <span className="text-slate-500">解讀：</span>
                        {ind.howToRead}
                      </p>
                    </li>
                  ))}
                </ul>
              </section>

              {/* 方法論限制 */}
              <section>
                <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-300 mb-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  方法論限制
                </h3>
                <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
                  {tutorial.limitations}
                </p>
              </section>

              {/* 科學性評估 */}
              <section>
                <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-300 mb-2">
                  <FlaskConical className="w-4 h-4 text-cyan-400" />
                  科學性評估
                </h3>
                <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
                  {tutorial.scientificNote}
                </p>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
