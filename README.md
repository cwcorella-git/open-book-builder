# Open Book Builder

A desktop + web app for visualizing, verifying, and sourcing
[The Open Book](https://github.com/joeycastillo/The-Open-Book) — Joey
Castillo's open-source e-reader (Raspberry Pi Pico + 4.2" B&W e-paper +
dual AAA, CC-BY-SA 4.0).

Ships as a Tauri desktop app and a static web build so the unified
parts list, assembly guide, and 3D board views can be shared with anyone.

**Live:** [cwcorella-git.github.io/open-book-builder](https://cwcorella-git.github.io/open-book-builder/)

## Why this exists

The upstream project's documentation is scattered across several BOMs,
a README with outdated file references, and a vision doc describing a
different board revision. Before sending money to PCBWay or Digi-Key,
this tool provides **one place** that shows:

1. What every component does and what it costs.
2. A unified parts list across both boards.
3. Interactive 3D views of the Main Board and E-Paper Driver module.
4. Step-by-step assembly instructions with component highlighting.
5. An ordering guide with current PCB specs and display info.
6. A Digi-Key BOM Manager CSV export for sourcing.

## What it looks like

Four tabs: **Board** (3D viewport + detail panel), **Parts List**
(table + Digi-Key CSV export), **Assembly** (step checklist + mini 3D
viewport), **About** (ordering guide + project status).

**Board tab** — renders both the Main Board (C1, from KiCad) and the
E-Paper Driver (C2, from EAGLE) with orbit controls, click-to-select,
side filtering, signal-type coloring, copper trace overlay, and five
procedural hero meshes (Pi Pico, C2 submodule, battery holder, microSD
slot, e-paper panel). Silkscreen overlays from both KiCad and EAGLE
source files render on each board face.

**Parts List tab** — 23 parts across both boards with build-qty
multiplier, optional-line toggle, and cost footer. Per-unit cost totals
$43.27 (E-Paper Driver assembly is $30–80 additional). The **Export
Digi-Key CSV** button writes a ready-to-upload file honoring qty and
optional toggles.

**Assembly tab** — 13 ordered build steps from bare boards to working
e-reader. Each step shows the relevant components, tools, and timing.
Clicking a step highlights its components in a mini 3D viewport while
dimming everything else, and orbits the camera to frame the relevant
parts (flipping to the correct board side). Progress persists via
localStorage.

**About tab** — what the Open Book is, ordering guide (gerber files,
PCB specs, display sourcing), what this app does, project status
(display EOL, firmware, Open Book Touch), credits, developer info.

## Architecture

### Dual-target build model

The same React app runs under Tauri (reading files via `invoke`) and as
a static site (reading a pre-baked JSON bundle). The boundary is a
single function:

```ts
// src/lib/dataset-source.ts
export async function loadBoardDataset(): Promise<BoardDataset> {
  if (isTauri()) {
    const { invoke } = await import('@tauri-apps/api/core');
    return invoke<BoardDataset>('load_board_dataset');
  }
  const res = await fetch(`${import.meta.env.BASE_URL}board-dataset.json`);
  if (!res.ok) throw new Error(`Failed to load board-dataset.json: ${res.status}`);
  return res.json();
}
```

`scripts/bake-dataset.ts` shells out to the Rust binary's `--export-json`
mode and writes `public/board-dataset.json` for the web target. Tauri
desktop reads the same data live via the `load_board_dataset` command.

### Why `include_str!`

Static data (`assembly.json`, `component_functions.json`,
both BOM CSVs) is bundled into the Rust binary via `include_str!` at
compile time. This means:

- `tauri dev`, bundled release, and `--export-json` all behave
  identically.
- No runtime filesystem reads for canonical data.
- No "where does this app expect its data directory?" question.

Parsed KiCad / EAGLE files are treated the same way — the C1
`.kicad_pcb` (1.3 MB) is copied into `src-tauri/data/` and
`include_str!`'d by `kicad_pcb.rs`; the C2 `.brd` (58 KB) sits next to
it and is read by `eagle.rs`.

### Tech stack

| Layer | Choice |
| --- | --- |
| Desktop shell | Tauri v2 |
| Frontend | React 19 + TypeScript 5.8 + Vite 7 |
| 3D | Three.js 0.183 + OrbitControls |
| KiCad parsing | `lexpr` 0.2 (S-expr walker) |
| EAGLE parsing | `quick-xml` 0.36 (manual Reader event loop) |
| BOM parsing | Rust `csv` crate |
| Errors | `thiserror` |

No database. No HTTP server.

## Project layout

```
open-book-builder/
├── index.html                        # Vite entry
├── package.json                      # scripts: dev, dev:web, build, build:web, preview, preview:web, tauri, bake-dataset
├── screenshots.mjs                   # Playwright screenshot automation for responsive testing
├── vite.config.ts
├── public/                           # baked board-dataset.json lands here (gitignored)
├── scripts/
│   └── bake-dataset.ts               # Shells `cargo run -- --export-json public/board-dataset.json`
│
├── src/
│   ├── main.tsx                      # React 19 ReactDOM.createRoot
│   ├── App.tsx                       # Tabbed shell (Board / Parts List / Assembly / About)
│   ├── lib/
│   │   ├── types.ts                  # Mirrors src-tauri/src/types.rs
│   │   ├── dataset-source.ts         # Tauri-vs-web boundary (isTauri())
│   │   ├── dataset-context.tsx       # React context + useDataset() hook
│   │   ├── navigation-context.tsx   # Tab / board / selection state + cross-tab navigation
│   │   ├── use-persisted-state.ts    # Generic localStorage-backed useState
│   │   ├── use-assembly-progress.ts  # Assembly checkbox state + progress aggregates
│   │   ├── digikey-csv.ts            # Pure Digi-Key BOM CSV builder + summary
│   │   ├── exporter.ts              # saveTextFile(): Tauri save-dialog vs web Blob
│   │   ├── use-breakpoint.ts          # Responsive breakpoint hook (compact / medium / wide)
│   │   ├── hero-meshes.ts            # Procedural Three.js builders (Pico, C2 module, Keystone 1022, MEM2075, GDEW042T2)
│   │   └── scene-renderer.ts         # Three.js scene — board extrude + per-component meshes
│   └── components/
│       ├── BoardView.tsx             # Two-pane layout: 3D viewport + detail panel
│       ├── BoardViewport.tsx         # React wrapper around scene-renderer
│       ├── BomView.tsx               # Two-pane table + detail panel + CSV export
│       ├── AssemblyView.tsx          # Step checklist + mini viewport with multi-highlight
│       └── AboutView.tsx             # Ordering guide, project status, credits
│
└── src-tauri/
    ├── Cargo.toml
    ├── tauri.conf.json               # productName "Open Book Builder"
    ├── capabilities/default.json     # dialog:allow-open, dialog:allow-save, fs:allow-read-text-file, fs:allow-write-text-file
    ├── data/
    │   ├── component_functions.json  # 24 MPNs with function, datasheet, cost, heroMeshId, distributor PNs (DK / Mouser / LCSC)
    │   ├── assembly.json             # 13 ordered build steps
    │   ├── hero-meshes/              # GLB assets for procedural hero mesh overrides
    │   ├── bom-c1-main.csv           # from upstream OSO-BOOK-C1/1-click-bom.csv
    │   ├── bom-c2-driver.csv         # from upstream OSO-BOOK-C2-02 (PCBWay)
    │   ├── OSO-BOOK-C1.kicad_pcb     # from upstream OSO-BOOK-C1 (1.3 MB, KiCad 6)
    │   └── OSO-BOOK-C2-02.brd        # from upstream OSO-BOOK-C2 (58 KB, EAGLE 9.6.2)
    └── src/
        ├── main.rs                   # Dispatches --export-json vs Tauri run
        ├── lib.rs                    # load_board_dataset cmd + export_json_to_path
        ├── types.rs                  # Serde mirrors with kebab-case enums
        ├── dataset.rs                # Glues static JSONs + BOM CSVs + KiCad + EAGLE into BoardDataset
        ├── kicad_pcb.rs              # lexpr walker → components, mounting holes, Edge.Cuts
        ├── eagle.rs                  # quick-xml Reader → C2 components, holes, outline, nets + synthesized Display
        ├── footprint_heights.rs      # Part-class → 3D extrusion height lookup
        ├── net_category.rs           # Net-name heuristic classifier + dominant-category picker
        └── bom.rs                    # Two CSV parsers → Vec<BomLine>, cost summarizer
```

## Data model

The canonical shape is `BoardDataset` (see `src/lib/types.ts` and
`src-tauri/src/types.rs`). One JSON document contains:

- `boards: Record<BoardId, BoardData>` — per-board geometry (components,
  outline, nets). `c1-main` comes from the KiCad PCB; `c2-driver` comes
  from the EAGLE `.brd` plus a synthesized `Display` component that
  carries the GDEW042T2 hero mesh.
- `bom: BomLine[]` — unified list tagged with `board`, merged with
  per-MPN metadata (function, datasheet URL, unit cost).
- `assembly: AssemblyStep[]` — ordered, phase-tagged.
- `costSummary: { perUnitUsd, missingLineItems }` — non-optional C1
  lines only. E-Paper Driver internals are excluded because the module
  is priced as a single pre-assembled unit.

## Build and verification

```bash
# Install once
npm install

# Desktop dev
npm run tauri dev

# Frontend typecheck
npx tsc --noEmit

# Backend typecheck
cd src-tauri && cargo check

# Bake the dataset to JSON (used by the web target)
npm run bake-dataset        # writes public/board-dataset.json

# Web build — static dist/ under /open-book-builder/ subpath
npm run build:web           # bakes dataset, typechecks, vite build
npm run preview:web         # serves dist/ at http://localhost:4173/open-book-builder/
```

### GitHub Pages deploy

`.github/workflows/deploy.yml` auto-deploys on push to `main`. Runs
`npm run build:web`, uploads `dist/`, and deploys via
`actions/deploy-pages@v4`.

Live at <https://cwcorella-git.github.io/open-book-builder/>.

If you fork this repo, change the `--base=/open-book-builder/` in
`package.json` to match the fork's repo name.

### Sanity check

Expected values for the baked dataset:

- 23 BOM rows (16 Main Board + 7 E-Paper Driver)
- `costSummary.perUnitUsd ≈ 43.27`
- `costSummary.missingLineItems == ["OSO-BOOK-C2-01"]`
- 13 assembly steps
- `boards["c1-main"]`: 27 components, 4 `outline.holes`, 40 Edge.Cuts
  `outline.edgeSegments`, outline 85 × 115 mm, 296 traces, 76 vias
- `boards["c2-driver"]`: 18 components (17 EAGLE + 1 synthesized
  Display), 3 `outline.holes`, 4 `outline.edgeSegments`, outline
  17.272 × 23.876 mm, 21 nets, 153 traces

## Upstream source files

Read-only inputs (not modified by this project):

- `The-Open-Book/OSO-BOOK-C1/` — `1-click-bom.csv`, `.kicad_pcb`,
  `.kicad_sch`
- `The-Open-Book/Fabrication Files/Castellated E-Paper Driver/OSO-BOOK-C2-02 (PCBWay)/`
  — `.brd`, `.sch`, BOM CSV

## License

Code: MIT. Visualization data derives from the upstream
[CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) work.
