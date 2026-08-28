/**
 * useInView — 懶加載 hook，檢測元素是否進入視口。
 *
 * 使用 IntersectionObserver 監聽目標元素，當元素進入視口時返回 true。
 * 一旦進入過視口後保持 true（不會因滾出視口而重置），適合懶加載場景。
 *
 * @param options IntersectionObserver 配置項
 * @returns [ref, inView] 元組 — ref 綁定到目標元素，inView 表示是否已進入視口
 */
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

type UseInViewOptions = {
  root?: Element | null;
  rootMargin?: string;
  threshold?: number | number[];
  /** 一旦進入視口後是否保持 true（默認 true，適合懶加載） */
  once?: boolean;
};

export function useInView<T extends HTMLElement = HTMLDivElement>(
  options: UseInViewOptions = {}
): [React.RefObject<T | null>, boolean] {
  const { root = null, rootMargin = '100px', threshold = 0.01, once = true } = options;
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // 如果已經 inView 且 once=true，不再監聽
    if (inView && once) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setInView(true);
            if (once) {
              observer.disconnect();
            }
          } else if (!once) {
            setInView(false);
          }
        }
      },
      { root, rootMargin, threshold }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [inView, once, root, rootMargin, threshold]);

  return [ref, inView];
}
