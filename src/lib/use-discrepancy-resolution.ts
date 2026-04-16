import { useCallback, useMemo } from 'react';
import type { Discrepancy } from './types';
import { usePersistedState } from './use-persisted-state';

const STORAGE_KEY = 'obb.resolvedDiscrepancies';

export interface DiscrepancyResolution {
  /** True iff the user has ticked the Resolved checkbox on this card. */
  isResolved: (id: string) => boolean;
  setResolved: (id: string, value: boolean) => void;
  /** Un-ticked build-critical items. Drives the header banner. */
  unresolvedBuildCritical: Discrepancy[];
}

/**
 * Wraps localStorage-backed resolution state around the discrepancy list.
 * Keyed by stable `discrepancy.id` so the user's progress survives data
 * updates (new discrepancies just default to unresolved).
 */
export function useDiscrepancyResolution(
  discrepancies: Discrepancy[],
): DiscrepancyResolution {
  const [resolved, setResolved] = usePersistedState<Record<string, boolean>>(
    STORAGE_KEY,
    {},
  );

  const isResolved = useCallback(
    (id: string) => Boolean(resolved[id]),
    [resolved],
  );

  const setOne = useCallback(
    (id: string, value: boolean) => {
      setResolved((prev) => {
        if (Boolean(prev[id]) === value) return prev;
        const next = { ...prev };
        if (value) next[id] = true;
        else delete next[id];
        return next;
      });
    },
    [setResolved],
  );

  const unresolvedBuildCritical = useMemo(
    () =>
      discrepancies.filter(
        (d) => d.severity === 'build-critical' && !resolved[d.id],
      ),
    [discrepancies, resolved],
  );

  return {
    isResolved,
    setResolved: setOne,
    unresolvedBuildCritical,
  };
}
