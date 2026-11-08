import { useCallback, useEffect, useRef, useState } from 'react';
import type { ApiError } from '@/types';

interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
}

export function toApiError(error: unknown): ApiError {
  if (error && typeof error === 'object' && 'status' in error && 'detail' in error) {
    return error as ApiError;
  }
  return { status: 0, detail: 'Request failed. Please retry.' };
}

export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[] = []
): QueryState<T> & { refetch: () => void } {
  const [state, setState] = useState<QueryState<T>>({
    data: null,
    loading: true,
    error: null,
  });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const depsKey = JSON.stringify(deps);
  const runIdRef = useRef(0);

  const run = useCallback(() => {
    const id = ++runIdRef.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    fnRef
      .current()
      .then((data) => {
        if (runIdRef.current === id) setState({ data, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (runIdRef.current === id) setState({ data: null, loading: false, error: toApiError(error) });
      });
  }, []);

  useEffect(() => {
    run();
    return () => { ++runIdRef.current; };
  }, [depsKey, run]);

  return { ...state, refetch: run };
}

export function useMutation<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>
) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const mutate = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      setLoading(true);
      setError(null);
      try {
        const result = await fn(...args);
        setLoading(false);
        return result;
      } catch (e) {
        const err = toApiError(e);
        setError(err);
        setLoading(false);
        return null;
      }
    },
    [fn]
  );

  return { mutate, loading, error, setError };
}

export function usePolling(
  active: boolean,
  fn: () => Promise<void>,
  intervalMs: number
) {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    if (!active) return;
    let stopped = false;
    const tick = async () => {
      try {
        await fnRef.current();
      } catch {
        // swallow polling errors
      }
      if (!stopped) {
        timer = window.setTimeout(tick, intervalMs);
      }
    };
    let timer = window.setTimeout(tick, intervalMs);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [active, intervalMs]);
}
