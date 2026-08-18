/**
 * @file AgentScoreTrend 組件 — 評分趨勢迷你折線圖（純 SVG 實現，無第三方依賴）。
 */
'use client';

import type { AgentIteration } from '@/lib/api/types';

interface Props {
  iterations: AgentIteration[];
  bestScore: number;
  bestIteration: number;
}

/**
 * 評分趨勢迷你折線圖（純 SVG，無依賴）。
 * @param iterations 歷史迭代列表
 * @param bestScore 歷史最佳評分
 * @param bestIteration 最佳評分所在輪次
 */
export function AgentScoreTrend({ iterations, bestScore, bestIteration }: Props) {
  if (iterations.length === 0) {
    return null;
  }

  // 按輪次排序（歷史 API 返回的是倒序，這裡反轉）
  const sorted = [...iterations].sort((a, b) => a.iteration - b.iteration);
  const scores = sorted.map((it) => it.composite_score);

  const width = 280;
  const height = 60;
  const padding = 8;

  const minScore = Math.min(...scores, 0);
  const maxScore = Math.max(...scores, bestScore, 50);
  const range = maxScore - minScore || 1;

  const points = scores.map((score, idx) => {
    const x = padding + (idx / Math.max(scores.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - ((score - minScore) / range) * (height - padding * 2);
    return { x, y, score, iteration: sorted[idx].iteration };
  });

  const pathD = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const areaD = `${pathD} L ${points[points.length - 1].x.toFixed(1)} ${height - padding} L ${padding} ${height - padding} Z`;

  // 最佳點
  const bestPoint = points.find((p) => p.iteration === bestIteration);

  return (
    <div className="rounded-lg border border-border bg-bg-base/50 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-muted">評分趨勢</span>
        <span className="text-xs text-amber-400">
          最佳: {bestScore > -999 ? bestScore.toFixed(1) : '-'} (第{bestIteration || '-'}輪)
        </span>
      </div>
      <svg width={width} height={height} className="w-full">
        <defs>
          <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(251 191 36)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="rgb(251 191 36)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* 面積 */}
        <path d={areaD} fill="url(#scoreGradient)" />
        {/* 折線 */}
        <path d={pathD} fill="none" stroke="rgb(251 191 36)" strokeWidth="1.5" strokeLinejoin="round" />
        {/* 數據點 */}
        {points.map((p) => (
          <circle
            key={p.iteration}
            cx={p.x}
            cy={p.y}
            r={p.iteration === bestIteration ? 3 : 2}
            fill={p.iteration === bestIteration ? 'rgb(251 191 36)' : 'rgb(148 163 184)'}
            className={p.iteration === bestIteration ? '' : 'opacity-60'}
          />
        ))}
        {/* 最佳點標記 */}
        {bestPoint && (
          <text
            x={bestPoint.x}
            y={bestPoint.y - 6}
            textAnchor="middle"
            className="fill-amber-400 text-[8px]"
          >
            ★{bestPoint.score.toFixed(0)}
          </text>
        )}
      </svg>
      <div className="flex justify-between text-[10px] text-muted mt-1">
        <span>第{sorted[0].iteration}輪</span>
        <span>第{sorted[sorted.length - 1].iteration}輪</span>
      </div>
    </div>
  );
}
