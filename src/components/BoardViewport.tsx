// Thin React wrapper around `scene-renderer.ts`. The Three.js scene is
// long-lived and driven imperatively — `[boardData]` is the only dep that
// forces a full re-init, because changing boards changes the entire mesh
// topology. Side filter + selection ride through `setSideFilter` /
// `setSelectedRef` on the live scene state.
//
// Mirrors /home/user/Projects/dodec-mapper/src/components/Viewport.tsx for
// its ref-based mount + React 19 StrictMode safety.

import { useEffect, useRef } from 'react';
import { initScene, type ColorMode, type SceneState, type SideFilter } from '../lib/scene-renderer';
import type { BoardData } from '../lib/types';

interface BoardViewportProps {
  boardData: BoardData;
  sideFilter: SideFilter;
  selectedRef: string | null;
  onSelect: (ref: string | null) => void;
  /**
   * Optional set of component refs to multi-highlight (Assembly view).
   * Non-null + non-empty dims everything else; null / empty reverts to the
   * normal board rendering. Identity doesn't need to be stable — the
   * scene-renderer dedupes + sorts into a key internally and no-ops when
   * unchanged.
   */
  highlightedRefs?: ReadonlyArray<string> | null;
  colorMode?: ColorMode;
  showTraces?: boolean;
}

export function BoardViewport({
  boardData,
  sideFilter,
  selectedRef,
  onSelect,
  highlightedRefs,
  colorMode,
  showTraces,
}: BoardViewportProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SceneState | null>(null);

  // Full re-init when the underlying board topology changes. Pull in the
  // current sideFilter/selectedRef/highlightedRefs as *initial* values so the
  // scene renders them on first paint; subsequent changes route through the
  // other effects.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const state = initScene(
      container,
      boardData,
      sideFilter,
      selectedRef,
      highlightedRefs ?? null,
    );
    state.onSelect = onSelect;
    sceneRef.current = state;

    return () => {
      state.dispose();
      sceneRef.current = null;
      // Explicit canvas removal — dispose() doesn't touch the DOM (dodec-
      // mapper convention).
      const canvas = container.querySelector('canvas');
      if (canvas) container.removeChild(canvas);
    };
    // boardData is the only structural dep. sideFilter / selectedRef /
    // onSelect / highlightedRefs wire through live-update effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boardData]);

  // Keep the click callback current without re-initializing the scene.
  useEffect(() => {
    if (sceneRef.current) sceneRef.current.onSelect = onSelect;
  }, [onSelect]);

  useEffect(() => {
    sceneRef.current?.setSideFilter(sideFilter);
  }, [sideFilter]);

  useEffect(() => {
    sceneRef.current?.setSelectedRef(selectedRef);
  }, [selectedRef]);

  useEffect(() => {
    sceneRef.current?.setHighlightedRefs(highlightedRefs ?? null);
  }, [highlightedRefs]);

  useEffect(() => {
    sceneRef.current?.setColorMode(colorMode ?? 'side');
  }, [colorMode]);

  useEffect(() => {
    sceneRef.current?.setTracesVisible(showTraces ?? false);
  }, [showTraces]);

  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        minHeight: 0,
        position: 'relative',
        border: '1px solid #1e293b',
        borderRadius: '6px',
        background: '#0b1220',
        overflow: 'hidden',
      }}
    />
  );
}
