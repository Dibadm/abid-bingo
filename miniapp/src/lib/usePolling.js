import { useEffect, useState, useRef, useCallback } from 'react';

export function usePolling(fetchFn, options = {}) {
  const {
    interval = 5000,
    backoffMax = 60000,
    backoffFactor = 2,
    immediate = true,
  } = options;

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const currentIntervalRef = useRef(interval);
  const timerRef = useRef(null);
  const mountedRef = useRef(true);
  const inFlightRef = useRef(false);
  const optsRef = useRef({ interval, backoffMax, backoffFactor });

  useEffect(() => {
    optsRef.current = { interval, backoffMax, backoffFactor };
  }, [interval, backoffMax, backoffFactor]);

  const execute = useCallback(async () => {
    if (!mountedRef.current || inFlightRef.current) return;
    inFlightRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      if (mountedRef.current) {
        setData(result);
        setError(null);
        currentIntervalRef.current = optsRef.current.interval;
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
        currentIntervalRef.current = Math.min(
          currentIntervalRef.current * optsRef.current.backoffFactor,
          optsRef.current.backoffMax
        );
      }
    } finally {
      setLoading(false);
      inFlightRef.current = false;
      if (mountedRef.current) {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(execute, currentIntervalRef.current);
      }
    }
  }, [fetchFn, backoffFactor, backoffMax]);

  useEffect(() => {
    mountedRef.current = true;
    if (immediate) {
      execute();
    } else {
      timerRef.current = setTimeout(execute, currentIntervalRef.current);
    }
    return () => {
      mountedRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [execute, immediate]);

  const resetBackoff = useCallback(() => {
    currentIntervalRef.current = optsRef.current.interval;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (mountedRef.current) {
      timerRef.current = setTimeout(execute, currentIntervalRef.current);
    }
  }, [execute]);

  return { data, error, loading, resetBackoff, execute };
}
