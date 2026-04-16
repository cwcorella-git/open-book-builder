import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * `useState` that round-trips through `localStorage`. Initial read is
 * synchronous (so consumers don't flicker), writes are batched in an effect.
 * Corrupt / unparseable stored values fall back to `initial` without
 * throwing; a warning goes to the console.
 */
export function usePersistedState<T>(
  key: string,
  initial: T,
): [T, (value: T | ((prev: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initial;
    try {
      const raw = window.localStorage.getItem(key);
      if (raw === null) return initial;
      return JSON.parse(raw) as T;
    } catch (err) {
      console.warn(`usePersistedState: failed to parse "${key}"; resetting.`, err);
      return initial;
    }
  });

  // Capture the latest key in a ref so the effect can detect rename
  // without re-running on unrelated re-renders.
  const keyRef = useRef(key);
  useEffect(() => {
    keyRef.current = key;
  }, [key]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(keyRef.current, JSON.stringify(value));
    } catch (err) {
      console.warn(`usePersistedState: failed to persist "${keyRef.current}".`, err);
    }
  }, [value]);

  const set = useCallback((next: T | ((prev: T) => T)) => {
    setValue(next);
  }, []);

  return [value, set];
}
