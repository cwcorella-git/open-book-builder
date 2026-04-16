/**
 * Bake the BoardDataset to `public/board-dataset.json` for the static web build.
 *
 * Shells out to the Rust binary's `--export-json` CLI mode. The web target
 * reads this file via `fetch(`${import.meta.env.BASE_URL}board-dataset.json`)`
 * in `src/lib/dataset-source.ts`; under Tauri the same data is served live
 * via `load_board_dataset` and this file is ignored.
 *
 * Uses a debug build — the emitter is just `serde_json::to_string_pretty`
 * over already-parsed data, so release speed-up is irrelevant and keeping
 * debug means cargo's incremental cache stays warm across runs.
 */

import { spawnSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..');
const tauriDir = resolve(repoRoot, 'src-tauri');
const outDir = resolve(repoRoot, 'public');
const outPath = resolve(outDir, 'board-dataset.json');

mkdirSync(outDir, { recursive: true });

const result = spawnSync(
  'cargo',
  ['run', '--quiet', '--bin', 'open-book-builder', '--', '--export-json', outPath],
  { cwd: tauriDir, stdio: ['ignore', 'inherit', 'inherit'] },
);

if (result.error) {
  console.error(`bake-dataset: failed to spawn cargo: ${result.error.message}`);
  process.exit(1);
}
if (result.status !== 0) {
  console.error(`bake-dataset: cargo exited with ${result.status}`);
  process.exit(result.status ?? 1);
}
console.error(`bake-dataset: wrote ${outPath}`);
