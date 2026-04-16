import type { BoardDataset } from './types';

/**
 * Abstraction over the two runtime targets:
 * - Tauri desktop: call the Rust `load_board_dataset` command via `invoke`.
 * - Static web: fetch the pre-baked `/board-dataset.json` emitted by
 *   `scripts/bake-dataset.ts`.
 *
 * The detection uses `window.__TAURI_INTERNALS__` because `@tauri-apps/api`
 * v2 sets that global; `window.__TAURI__` still works for older clients.
 */
export async function loadBoardDataset(): Promise<BoardDataset> {
  if (isTauri()) {
    const { invoke } = await import('@tauri-apps/api/core');
    return invoke<BoardDataset>('load_board_dataset');
  }
  const res = await fetch(`${import.meta.env.BASE_URL}board-dataset.json`);
  if (!res.ok) {
    throw new Error(`Failed to load board-dataset.json: ${res.status}`);
  }
  return res.json();
}

export function isTauri(): boolean {
  return (
    typeof window !== 'undefined' &&
    (window.__TAURI__ !== undefined || window.__TAURI_INTERNALS__ !== undefined)
  );
}
