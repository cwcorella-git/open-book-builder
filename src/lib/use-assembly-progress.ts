import { useCallback, useMemo } from 'react';
import type { AssemblyStep } from './types';
import { usePersistedState } from './use-persisted-state';

const STORAGE_KEY = 'obb.assemblyStepProgress';

export interface AssemblyProgress {
  /** True iff the user has ticked the checkbox on this step. */
  isCompleted: (id: string) => boolean;
  setCompleted: (id: string, value: boolean) => void;
  completedCount: number;
  totalCount: number;
  /** Sum of `estimatedMinutes ?? 0` over uncompleted steps. */
  totalMinutesRemaining: number;
  /**
   * First step (by `order`) that the user hasn't ticked. Returns null when
   * every step is complete. Used to default the active step on mount.
   */
  firstUncompletedStep: () => AssemblyStep | null;
}

/**
 * localStorage-backed completion state for the Assembly tab. Sibling of
 * `useDiscrepancyResolution` — same `usePersistedState` primitive, same
 * `obb.*` key convention. Keyed by stable `step.id` so new authored steps
 * default to uncompleted and the user's progress survives data updates.
 */
export function useAssemblyProgress(steps: AssemblyStep[]): AssemblyProgress {
  const [completed, setCompletedMap] = usePersistedState<Record<string, boolean>>(
    STORAGE_KEY,
    {},
  );

  const isCompleted = useCallback(
    (id: string) => Boolean(completed[id]),
    [completed],
  );

  const setOne = useCallback(
    (id: string, value: boolean) => {
      setCompletedMap((prev) => {
        if (Boolean(prev[id]) === value) return prev;
        const next = { ...prev };
        if (value) next[id] = true;
        else delete next[id];
        return next;
      });
    },
    [setCompletedMap],
  );

  const completedCount = useMemo(
    () => steps.reduce((n, s) => (completed[s.id] ? n + 1 : n), 0),
    [steps, completed],
  );

  const totalMinutesRemaining = useMemo(
    () =>
      steps.reduce(
        (sum, s) => (completed[s.id] ? sum : sum + (s.estimatedMinutes ?? 0)),
        0,
      ),
    [steps, completed],
  );

  // Callable accessor so consumers can re-evaluate after state transitions
  // (e.g., advancing the active step when one is ticked complete) without
  // resubscribing to the memo.
  const firstUncompletedStep = useCallback((): AssemblyStep | null => {
    // `steps` is expected sorted by `order` from the caller.
    for (const s of steps) if (!completed[s.id]) return s;
    return null;
  }, [steps, completed]);

  return {
    isCompleted,
    setCompleted: setOne,
    completedCount,
    totalCount: steps.length,
    totalMinutesRemaining,
    firstUncompletedStep,
  };
}
