import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook with built-in AbortController request cancellation
 * to prevent race conditions during fast typing / rapid tab switching.
 */
export function useCancelableApi<T, P extends any[]>(
  apiFn: (...args: [...P, AbortSignal]) => Promise<T>
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const execute = useCallback(
    async (...args: P) => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      setLoading(true);
      setError(null);

      try {
        const result = await apiFn(...args, controller.signal);
        if (!controller.signal.aborted) {
          setData(result);
          setLoading(false);
        }
      } catch (err: any) {
        if (err.name === 'CanceledError' || err.name === 'AbortError') {
          // Request was intentionally canceled, ignore
          return;
        }
        if (!controller.signal.aborted) {
          setError(err.message || 'An unexpected error occurred');
          setLoading(false);
        }
      }
    },
    [apiFn]
  );

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return { data, loading, error, execute, setData };
}
