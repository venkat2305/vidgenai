import { useEffect, useRef, useCallback } from 'react';

interface UseVideoIntersectionProps {
  onVideoEnter: (id: string) => void;
  onVideoLeave: (id: string) => void;
  threshold?: number;
  rootMargin?: string;
}

export function useVideoIntersection({
  onVideoEnter,
  onVideoLeave,
  threshold = 0.7,
  rootMargin = '-10% 0px'
}: UseVideoIntersectionProps) {
  const observerRef = useRef<IntersectionObserver | null>(null);
  const elementsRef = useRef<Map<string, Element>>(new Map());

  const observeElement = useCallback((id: string, element: Element) => {
    if (observerRef.current && element) {
      elementsRef.current.set(id, element);
      observerRef.current.observe(element);
    }
  }, []);

  const unobserveElement = useCallback((id: string) => {
    const element = elementsRef.current.get(id);
    if (observerRef.current && element) {
      observerRef.current.unobserve(element);
      elementsRef.current.delete(id);
    }
  }, []);

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const id = entry.target.getAttribute('data-video-id');
          if (id) {
            if (entry.isIntersecting) {
              onVideoEnter(id);
            } else {
              onVideoLeave(id);
            }
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
  }, [onVideoEnter, onVideoLeave, threshold, rootMargin]);

  return {
    observeElement,
    unobserveElement
  };
}