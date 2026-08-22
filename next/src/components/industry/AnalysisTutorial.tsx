/**
 * @file AnalysisTutorial 進階分析教學組件 —
 * 右上角「？」圖標按鈕，點擊展開/收起該視圖的教學面板，
 * 內容包含原理、指標含義、方法論限制與科學性評估。
 * 教學內容來自 `@/lib/analysis-tutorials` 的 ANALYSIS_TUTORIALS。
 */
'use client';

import { useState } from 'react';
import { HelpCircle, ChevronDown, BookOpen, AlertTriangle, FlaskConical, Lightbulb } from 'lucide-react';
import { ANALYSIS_TUTORIALS } from '@/lib/analysis-tutorials';

interface Props {
  /** 對應 ANALYSIS_TUTORIALS 中的 key */
  tutorialKey: string;
}

/**
 * AnalysisTutorial 組件 — 在進階分析視圖中提供可摺疊的教學面板。
 * 若 tutorialKey 在 ANALYSIS_TUTORIALS 中不存在，返回 null（不渲染任何內容）。
 */
export function AnalysisTutorial({ tutorialKey }: Props) {
  const [open, setOpen] = useState(false);
  const tutorial = ANALYSIS_TUTORIALS[tutorialKey];

  if (!tutorial) return null;

  return (
    <div className="w-full">
      {/* 觸發按鈕 */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-slate-400 hover:text-accent hover:bg-bg-hover transition-colors"
          aria-label={open ? '收起教學' : '展開教學'}
          title={open ? '收起教學' : '查看此視圖的教學說明'}
        >
          <HelpCircle className="w-4 h-4" />
          <span>{open ? '收起教學' : '教學'}</span>
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* 教學面板 */}
      {open && (
        <div className="mt-2 rounded-lg bg-slate-800/50 border border-border p-4 space-y-4 text-sm leading-relaxed">
          {/* 標題 */}
          <div className="flex items-center gap-2 pb-2 border-b border-border">
            <BookOpen className="w-4 h-4 text-accent" />
            <h3 className="text-base font-semibold text-slate-100">{tutorial.title}</h3>
          </div>

          {/* 原理 */}
          <section>
            <h4 className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
              <Lightbulb className="w-3.5 h-3.5 text-yellow-400" />
              原理
            </h4>
            <p className="text-slate-300">{tutorial.principle}</p>
          </section>

          {/* 指標含義 */}
          <section>
            <h4 className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 mb-2 uppercase tracking-wide">
              <BookOpen className="w-3.5 h-3.5 text-accent" />
              指標含義與解讀
            </h4>
            <ul className="space-y-2.5">
              {tutorial.indicators.map((ind, i) => (
                <li key={i} className="rounded-md bg-bg-panel/60 border border-border/60 p-2.5">
                  <p className="font-medium text-slate-100">{ind.name}</p>
                  <p className="text-slate-400 mt-1">
                    <span className="text-slate-500">含義：</span>
                    {ind.meaning}
                  </p>
                  <p className="text-slate-400 mt-0.5">
                    <span className="text-slate-500">解讀：</span>
                    {ind.howToRead}
                  </p>
                </li>
              ))}
            </ul>
          </section>

          {/* 方法論限制 */}
          <section>
            <h4 className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              方法論限制
            </h4>
            <p className="text-slate-300 whitespace-pre-line">{tutorial.limitations}</p>
          </section>

          {/* 科學性評估 */}
          <section>
            <h4 className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
              <FlaskConical className="w-3.5 h-3.5 text-cyan-400" />
              科學性評估
            </h4>
            <p className="text-slate-300 whitespace-pre-line">{tutorial.scientificNote}</p>
          </section>
        </div>
      )}
    </div>
  );
}
