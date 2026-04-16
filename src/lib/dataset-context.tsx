import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { BoardDataset } from './types';
import { loadBoardDataset } from './dataset-source';

type Status =
  | { kind: 'loading' }
  | { kind: 'ready'; dataset: BoardDataset }
  | { kind: 'error'; message: string };

const Ctx = createContext<Status>({ kind: 'loading' });

export function DatasetProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>({ kind: 'loading' });

  useEffect(() => {
    let cancelled = false;
    loadBoardDataset()
      .then((dataset) => { if (!cancelled) setStatus({ kind: 'ready', dataset }); })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : String(err);
        setStatus({ kind: 'error', message });
      });
    return () => { cancelled = true; };
  }, []);

  return <Ctx.Provider value={status}>{children}</Ctx.Provider>;
}

/** Returns the loaded dataset, or throws if called while still loading/erroring.
 *  Wrap consumers in `<RequireDataset>` so this contract holds. */
export function useDataset(): BoardDataset {
  const s = useContext(Ctx);
  if (s.kind !== 'ready') {
    throw new Error('useDataset called before dataset was ready');
  }
  return s.dataset;
}

export function useDatasetStatus(): Status {
  return useContext(Ctx);
}
