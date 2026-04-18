// Shared viewport configuration state. Each tab sets viewport properties
// on mount (visibility, click behavior, highlight refs) and the persistent
// ViewportColumn in App.tsx reads them to drive the single BoardViewport.

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { SideFilter, ColorMode } from './scene-renderer';

export interface ViewportConfig {
  sideFilter: SideFilter;
  colorMode: ColorMode;
  showTraces: boolean;
  highlightedRefs: ReadonlyArray<string> | null;
  clickSelectEnabled: boolean;
  focusRefs: ReadonlyArray<string> | null;
  visible: boolean;
}

export interface ViewportApi {
  config: ViewportConfig;
  setConfig: (patch: Partial<ViewportConfig>) => void;
}

const DEFAULT_CONFIG: ViewportConfig = {
  sideFilter: 'both',
  colorMode: 'side',
  showTraces: false,
  highlightedRefs: null,
  clickSelectEnabled: true,
  focusRefs: null,
  visible: true,
};

const ViewportCtx = createContext<ViewportApi | null>(null);

export function ViewportProvider({ children }: { children: ReactNode }) {
  const [config, setConfigState] = useState<ViewportConfig>(DEFAULT_CONFIG);

  const setConfig = useCallback((patch: Partial<ViewportConfig>) => {
    setConfigState((prev) => ({ ...prev, ...patch }));
  }, []);

  const api = useMemo<ViewportApi>(
    () => ({ config, setConfig }),
    [config, setConfig],
  );

  return <ViewportCtx.Provider value={api}>{children}</ViewportCtx.Provider>;
}

export function useViewport(): ViewportApi {
  const ctx = useContext(ViewportCtx);
  if (!ctx) {
    throw new Error('useViewport called outside ViewportProvider');
  }
  return ctx;
}
