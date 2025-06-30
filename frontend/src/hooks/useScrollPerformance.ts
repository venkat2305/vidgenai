import { useEffect, useRef, useCallback } from 'react';

interface UseScrollPerformanceOptions {
  enabled?: boolean;
  threshold?: number;
  rootMargin?: string;
}

export function useScrollPerformance({
  enabled = true,
  threshold = 0.1,
  rootMargin = '50px'
}: UseScrollPerformanceOptions = {}) {
  const observerRef = useRef<IntersectionObserver | null>(null);
  const elementsMap = useRef<Map<Element, () => void>>(new Map());

  const observeElement = useCallback((element: Element, callback: () => void) => {
    if (!enabled || !observerRef.current) return;
    
    elementsMap.current.set(element, callback);
    observerRef.current.observe(element);
  }, [enabled]);

  const unobserveElement = useCallback((element: Element) => {
    if (!observerRef.current) return;
    
    observerRef.current.unobserve(element);
    elementsMap.current.delete(element);
  }, []);

  useEffect(() => {
    if (!enabled) return;

    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const callback = elementsMap.current.get(entry.target);
          if (callback && entry.isIntersecting) {
            callback();
          }
        });
      },
      {
        threshold,
        rootMargin
      }
    );

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [enabled, threshold, rootMargin]);

  return {
    observeElement,
    unobserveElement
  };
}