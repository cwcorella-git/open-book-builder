// Shared navigation state — lifts tab/board/selectedRef out of individual
// tab components so cross-tab moves ("click a ref chip in Assembly, jump to
// Board with that ref selected") have a single place to fire through.
//
// Mirrors the shape of `dataset-context.tsx`: a Context + Provider + typed
// hook. Sits as a peer of DatasetProvider (consumes it, so it must render
// inside). No persistence — selection state is session-only.

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useDatasetStatus } from './dataset-context';
import type { BoardId } from './types';

export type Tab = 'board' | 'bom' | 'assembly' | 'discrepancies' | 'about';

interface NavigationApi {
  tab: Tab;
  board: BoardId;
  selectedRef: string | null;
  setTab: (tab: Tab) => void;
  setBoard: (board: BoardId) => void;
  selectComponent: (ref: string | null) => void;
  /** Cross-tab jump: resolve the board that owns `ref` and switch to Board
   *  tab with that ref selected. No-ops silently if the ref doesn't exist on
   *  either board. */
  navigateToComponent: (ref: string) => void;
}

const NavigationCtx = createContext<NavigationApi | null>(null);

export function NavigationProvider({ children }: { children: ReactNode }) {
  const datasetStatus = useDatasetStatus();
  const [tab, setTab] = useState<Tab>('bom');
  const [board, setBoard] = useState<BoardId>('c1-main');
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const selectComponent = useCallback((ref: string | null) => {
    setSelectedRef(ref);
  }, []);

  const navigateToComponent = useCallback(
    (ref: string) => {
      // Dataset must be loaded to resolve target board. In practice the chips
      // that trigger this are only rendered after the dataset is ready, so
      // this guard is belt-and-suspenders.
      if (datasetStatus.kind !== 'ready') return;
      const dataset = datasetStatus.dataset;

      // 1. Check each board's components directly — fastest path and handles
      //    the synthesized `Display` component (lives on C2, BOM row lives on
      //    C1, so the BOM fallback below would send us to the wrong board).
      const boardOrder: BoardId[] = ['c1-main', 'c2-driver'];
      let target: BoardId | null = null;
      for (const b of boardOrder) {
        if (dataset.boards[b].components.some((c) => c.ref === ref)) {
          target = b;
          break;
        }
      }
      // 2. Fall back to the BOM's board field.
      if (target === null) {
        const line = dataset.bom.find((l) => l.refs.includes(ref));
        if (line) target = line.board;
      }
      // 3. Still nothing → silent no-op.
      if (target === null) return;

      setBoard(target);
      setTab('board');
      setSelectedRef(ref);
    },
    [datasetStatus],
  );

  const api = useMemo<NavigationApi>(
    () => ({
      tab,
      board,
      selectedRef,
      setTab,
      setBoard,
      selectComponent,
      navigateToComponent,
    }),
    [tab, board, selectedRef, selectComponent, navigateToComponent],
  );

  return <NavigationCtx.Provider value={api}>{children}</NavigationCtx.Provider>;
}

export function useNavigation(): NavigationApi {
  const ctx = useContext(NavigationCtx);
  if (!ctx) {
    throw new Error('useNavigation called outside NavigationProvider');
  }
  return ctx;
}
