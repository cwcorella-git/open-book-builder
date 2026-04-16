# Open Book Builder

A desktop + web app for visualizing, verifying, and sourcing
[The Open Book](https://github.com/joeycastillo/The-Open-Book) — Joey
Castillo's open-source e-reader (Raspberry Pi Pico + GDEW042T2 4.2" e-paper +
dual AAA, CC-BY-SA 4.0).

This is a personal tool that also ships as a static web build so the unified
BOM, discrepancy list, and 3D visualization can be shared.

## Why this exists

Three primary source BOMs disagree in non-obvious ways, and the current
PCBWay order draft has two build-critical errors that would produce
unusable boards:

- **PCBWay thickness is set to 1.6 mm**, but the 3D-printed case
  expects **1.0 mm**. Boards ordered at 1.6 mm won't fit.
- **PCBWay surface finish is "HASL with lead"**, but the README specifies
  **lead-free HASL** (RoHS-compliant).

On top of that, the `why-the-open-book` vision doc describes the archived
ESP32-S3 design, not the shipping Pico build. `COGS-LIST` mixes annotations
from both boards (SRAM pull-ups, headphone biasing resistors — none of which
exist on the current C1). The April 2025 BOM omits the Keystone 1022C battery
retainer clip. COGS-LIST has a MOSFET line-total arithmetic error.

Before sending money to PCBWay or Digi-Key, the author wants **one place**
that shows:

1. What every component does and what it costs.
2. A reconciled, unified BOM across the three source BOMs.
3. The discrepancy inventory with a Resolved toggle.
4. A 3D visualization of both the C1 main board and the C2 castellated
   e-paper driver submodule.
5. A Digi-Key BOM Manager CSV export for sourcing.

## Current status

Tasks #1–#10 of the build plan are complete. The backend parses both BOM
CSVs + the C1 `.kicad_pcb` and merges everything with hand-authored per-MPN
metadata; the React shell renders the BOM view (build-qty multiplier,
optional-line toggle, cost footer, **Digi-Key CSV export button**), the
Discrepancy view (severity-colored cards, localStorage-persisted Resolved
toggle, red header banner for unresolved build-critical items), and a
**Three.js 3D viewport of the C1 main board** with orbit controls, a
top/bottom/both side filter, click-to-select raycaster picking, and
**four procedural hero meshes** for the visually dominant components
(Pi Pico U1, C2 submodule U2, Keystone 1022 battery holder BT1, MEM2075
microSD slot U3). **The sourcing loop is closed** — open app → resolve
build-critical items → Export CSV → upload to Digi-Key.
**The web target is live** at
[cwcorella-git.github.io/open-book-builder](https://cwcorella-git.github.io/open-book-builder/),
auto-deployed on push via `.github/workflows/deploy.yml`. The Assembly
tab still renders placeholder text.

**What works today:**

- `cargo build` + `./open-book-builder --export-json <path>` produces a
  complete, well-typed `BoardDataset` JSON.
- `npm run tauri dev` opens the desktop window. **BOM** tab and
  **Discrepancies** tab are fully functional.
- On first boot, the red banner surfaces the two PCBWay build-critical
  issues (thickness and leaded HASL). Flipping their Resolved toggles
  persists across reloads via `localStorage['obb.resolvedDiscrepancies']`.
- Per-unit cost totals **$43.27**, matching the April 2025 BOM figure.
- The only `missingLineItems` entry is `c1-main:OSO-BOOK-C2-01` — exactly
  the known discrepancy (`c2-module-cost-missing`).
- **Export Digi-Key CSV** writes `open-book-digikey-bom.csv` with 14
  sourceable lines at default toggles (9 skipped: all 7 C2-driver internals
  priced as a single PCBA, plus the GDEW042T2 panel and the
  OSO-BOOK-C2-01 module itself). Honors `qtyMultiplier` and
  `includeOptional`; dispatches through Tauri save-dialog on desktop and
  a Blob download on web — same CSV output on both paths.
- `npm run build:web` bakes the dataset, typechecks, and emits `dist/`
  under the `/open-book-builder/` subpath ready for GitHub Pages.
  `npm run preview:web` serves it locally at
  `http://localhost:4173/open-book-builder/` for smoke-testing. Plain
  `npm run build` stays root-relative so Tauri's desktop bundle is
  unaffected.
- **Board tab** renders the C1 outline as an extruded 1 mm PCB
  (85 × 115 mm rounded rectangle from Edge.Cuts, four mounting holes
  punched through) with 27 component meshes — 4 procedural hero meshes
  (U1 Pi Pico with castellations + USB-C housing + silkscreen label,
  U2 C2 submodule as a green castellated board with IC rectangles,
  BT1 Keystone 1022 as a plastic base with two AAA cylinders + gold
  contact bumps, U3 MEM2075 as a polished-steel microSD housing with
  visible slot) plus 23 extruded-bbox boxes for the passives and other
  parts. Part-class heights come from `footprint_heights.rs` (0.6 mm
  for 0805/1206 passives, 4.5 mm for JST PH connectors, 12 mm for the
  AAA battery holder, etc.) so parts don't all look like flat squares.
  Orbit-drag, scroll-zoom, and click-to-select all work; the highlighted
  mesh gets a white emissive tint and the right-hand detail panel shows
  position, footprint, 3D bbox, pad count, and the matching BOM line
  (MPN, function, unit cost, Digi-Key PN, datasheet link). The
  top/bottom/both side filter hides component meshes without touching
  the board. The C2 board shows an explicit "lands in task #11" empty
  state.

**What's mocked:**

- Silkscreen textures on the board faces (task #13 polish) — faces are
  a solid slate color right now.
- C2 castellated e-paper driver geometry (task #11, EAGLE parser). The
  GDEW042T2 display panel's hero mesh lives with that work since it
  physically belongs to the C2 submodule face.

See `Roadmap` below and the authoritative plan at
`~/.claude/plans/melodic-tinkering-newt.md`.

## Architecture

### Dual-target build model

The same React app runs under Tauri (reading files via `invoke`) and as a
static site (reading a pre-baked JSON bundle). The boundary is a single
function:

```ts
// src/lib/dataset-source.ts
export async function loadBoardDataset(): Promise<BoardDataset> {
  if (isTauri()) {
    const { invoke } = await import('@tauri-apps/api/core');
    return invoke<BoardDataset>('load_board_dataset');
  }
  const res = await fetch(`${import.meta.env.BASE_URL}board-dataset.json`);
  return res.json();
}
```

`scripts/bake-dataset.ts` shells out to the Rust binary's `--export-json`
mode and writes `public/board-dataset.json` for the web target. Tauri
desktop reads the same data live via the `load_board_dataset` command.

### Why `include_str!`

Static data (`discrepancies.json`, `assembly.json`, `component_functions.json`,
both BOM CSVs) is bundled into the Rust binary via `include_str!` at compile
time. This means:

- `tauri dev`, bundled release, and `--export-json` all behave identically.
- No runtime filesystem reads for canonical data.
- No "where does this app expect its data directory?" question.

Parsed KiCad / EAGLE files are treated the same way — the C1
`.kicad_pcb` (1.3 MB) is copied into `src-tauri/data/` and `include_str!`'d
by `kicad_pcb.rs`. The C2 `.brd` / `.sch` will follow suit in task #11.
The only awkward wrinkle: KiCad sprinkles `(tstamp <uuid>)` and
`(tedit <hex-epoch>)` atoms throughout, which lexpr's default reader
rejects as malformed numbers. `strip_timestamps()` removes both subexprs
before handing the text to lexpr — we never consume the values anyway.

### Tech stack

Mirrors `~/Projects/dodec-mapper/` with additions:

| Layer | Choice |
| --- | --- |
| Desktop shell | Tauri v2 |
| Frontend | React 19.1 + TypeScript 5.8 + Vite 7 |
| 3D | Three.js 0.183 + OrbitControls |
| KiCad parsing | `lexpr` 0.2 (generic S-expr walker — `kicad-parse-gen` is stale since 2018, `kiutils` isn't on crates.io) |
| EAGLE parsing (pending) | `quick-xml` + serde structs |
| BOM parsing | Rust `csv` crate |
| Errors | `thiserror` |

No database. No HTTP server. No Monaco. No xterm.

## Project layout

```
open-book-builder/
├── index.html                        # Vite entry, dark theme inline styles
├── package.json                      # scripts: dev, build, tauri, bake-dataset, build:web, preview:web
├── vite.config.ts                    # port 1423 (HMR 1424) to avoid dodec-mapper's 1421
├── public/                           # baked board-dataset.json lands here (gitignored)
├── scripts/
│   └── bake-dataset.ts               # Shells `cargo run -- --export-json public/board-dataset.json`
│
├── src/
│   ├── main.tsx                      # React 19 ReactDOM.createRoot
│   ├── App.tsx                       # Tabbed shell (Board / BOM / Assembly / Discrepancies)
│   ├── vite-env.d.ts                 # window.__TAURI__ globals
│   ├── lib/
│   │   ├── types.ts                       # Mirrors src-tauri/src/types.rs
│   │   ├── dataset-source.ts              # Tauri-vs-web boundary (isTauri())
│   │   ├── dataset-context.tsx            # React context + useDataset() hook
│   │   ├── use-persisted-state.ts         # Generic localStorage-backed useState
│   │   ├── use-discrepancy-resolution.ts  # Resolved-state wrapper, drives the banner
│   │   ├── digikey-csv.ts                 # Pure Digi-Key BOM CSV builder + summary
│   │   ├── exporter.ts                    # saveTextFile(): Tauri save-dialog vs web Blob
│   │   ├── hero-meshes.ts                 # Procedural Three.js builders (Pico, C2 module, Keystone 1022, MEM2075)
│   │   └── scene-renderer.ts              # Three.js scene — board extrude + per-component meshes
│   └── components/
│       ├── BoardView.tsx                  # Built. Two-pane layout: viewport + detail panel.
│       ├── BoardViewport.tsx              # Built. React wrapper around scene-renderer.
│       ├── BomView.tsx                    # Built. Two-pane table + detail panel + CSV export.
│       ├── DiscrepancyView.tsx            # Built. Severity-grouped cards, Resolved toggle.
│       └── DiscrepancyBanner.tsx          # Built. Red header bar; hidden when 0 unresolved.
│
└── src-tauri/
    ├── Cargo.toml
    ├── tauri.conf.json               # productName "Open Book Builder"
    ├── capabilities/default.json     # dialog:allow-save, fs:allow-write-text-file
    ├── data/
    │   ├── component_functions.json  # 17 MPNs with function, datasheet, cost, heroMeshId
    │   ├── discrepancies.json        # 12 entries covering the 4 severity levels
    │   ├── assembly.json             # 12 ordered build steps
    │   ├── bom-c1-main.csv           # copied from the-open-book/OSO-BOOK-C1/1-click-bom.csv
    │   ├── bom-c2-driver.csv         # copied from the-open-book/OSO-BOOK-C2-02 (PCBWay)
    │   └── OSO-BOOK-C1.kicad_pcb     # copied from the-open-book/OSO-BOOK-C1 (1.3 MB, KiCad 6)
    └── src/
        ├── main.rs                   # Dispatches --export-json vs Tauri run
        ├── lib.rs                    # load_board_dataset cmd + export_json_to_path
        ├── types.rs                  # Serde mirrors with kebab-case enums
        ├── dataset.rs                # Glues static JSONs + BOM CSVs + KiCad into BoardDataset
        ├── kicad_pcb.rs              # lexpr walker → components, mounting holes, Edge.Cuts
        ├── footprint_heights.rs      # Part-class → 3D extrusion height lookup
        └── bom.rs                    # Two CSV parsers → Vec<BomLine>, cost summarizer
```

## Data model

The canonical shape is `BoardDataset` (see `src/lib/types.ts` and
`src-tauri/src/types.rs`). One JSON document contains:

- `boards: Record<BoardId, BoardData>` — per-board geometry (components,
  outline, nets). `c1-main` is now fully populated from the KiCad PCB;
  `c2-driver` is still an empty stub pending the EAGLE parser (task #11).
  `nets` stays empty until task #13 parses `.kicad_sch`.
- `bom: BomLine[]` — unified list tagged with `board: 'c1-main' | 'c2-driver'`,
  merged with per-MPN metadata (function, datasheet URL, unit cost).
- `discrepancies: Discrepancy[]` — hand-authored, severity-classed.
- `assembly: AssemblyStep[]` — ordered, phase-tagged.
- `costSummary: { perUnitUsd, perTenUnitsUsd, missingLineItems }` —
  non-optional C1 lines only. C2 internals are excluded because the module
  is priced as a single PCBA unit (OSO-BOOK-C2-01).
- `bomComparison: BomComparison[]` — reserved; the three-way BOM diff
  UI hasn't landed yet.

### Why BoardId uses BTreeMap / `kebab-case`

Rust side: `boards: BTreeMap<BoardId, BoardData>` — `BTreeMap` gives stable
key ordering in the serialized JSON (important for reproducible `--export-json`
output). Serde `rename_all = "kebab-case"` makes the enum serialize as
`"c1-main"` and `"c2-driver"` on the wire, matching the TS string-literal
type.

### `ref` keyword workaround

`ref` is a Rust keyword, so the Component and NetPadRef structs use
`#[serde(rename = "ref")] pub ref_: String`. TS side just sees `ref: string`.

## Build and verification

```bash
# Install once
npm install

# Desktop dev
npm run tauri dev

# Frontend typecheck (runs automatically on build)
npx tsc --noEmit

# Backend typecheck
cd src-tauri && cargo check

# Bake the dataset to JSON (used by the web target; also driven by npm run build:web)
npm run bake-dataset        # writes public/board-dataset.json

# Web build — emits a static dist/ under the /open-book-builder/ subpath
npm run build:web           # bakes dataset, typechecks, vite build --base=/open-book-builder/
npm run preview:web         # serves dist/ locally at http://localhost:4173/open-book-builder/
```

### GitHub Pages deploy

`.github/workflows/deploy.yml` auto-deploys on push to `main`:

- Runs on `ubuntu-24.04`, installs Tauri v2 apt deps
  (`libwebkit2gtk-4.1-dev`, `libgtk-3-dev`,
  `libayatana-appindicator3-dev`, `librsvg2-dev`), caches npm + cargo.
- Runs `npm run build:web`, uploads `dist/` as the Pages artifact,
  deploys via `actions/deploy-pages@v4`.
- Cold-run ~4–6 min (cargo dominates); warm-cache runs ~60–90 s.
- Live at <https://cwcorella-git.github.io/open-book-builder/>.

If you fork this repo, also change the Vite `--base=/open-book-builder/`
in `package.json` to match the fork's repo name.

**Sanity check** the baked dataset (current expected output):

- 23 BOM rows (16 C1 + 7 C2)
- `costSummary.perUnitUsd ≈ 43.27` (matches April 2025 BOM)
- `costSummary.perTenUnitsUsd ≈ 432.70`
- `costSummary.missingLineItems == ["c1-main:OSO-BOOK-C2-01"]`
- 12 discrepancies, 12 assembly steps
- `boards["c1-main"]`: 27 components, 4 mounting holes, 40 Edge.Cuts
  segments, outline 85 × 115 mm; every component has a non-empty `bomRef`
  (JP1 / JP2 solder-jumpers are present in KiCad but not in the BOM,
  so the parser drops them — the ref-matching filter is the source of truth)
- `boards["c2-driver"]`: still empty until task #11

## Canonical discrepancies

Authored in `src-tauri/data/discrepancies.json`. These are the things the
BOM / README / vision-doc archaeology surfaced — baked into the dataset so
the Discrepancies view (task #5) can render them as severity-colored cards.

**Build-critical (2):**

- `pcbway-thickness` — 1.6 mm → 1.0 mm
- `pcbway-hasl-leaded` — HASL with lead → Lead-Free HASL (or ENIG)

**Cost-impact (3):**

- `c2-module-cost-missing` — no BOM includes C2 PCBA cost
- `cogs-list-mosfet-arithmetic` — $0.32 where $6.40 belongs
- `april2025-bom-missing-retainer` — missing Keystone 1022C retainer

**Naming (4):** MOSFET "M channel" typo, GDEW042T2 vs GDEY042T81 display,
Pico SC0915 vs SC0918 SKU, C2 boost-cap count mismatch.

**Informational (3):** `why-the-open-book` describes ESP32-S3 design;
COGS-LIST references SRAM and audio hardware from the older B1 board.

## Roadmap

The 13-task build plan lives at
`~/.claude/plans/melodic-tinkering-newt.md`. Status:

- [x] **#1** Scaffold project directory
- [x] **#2** Author static data JSONs (component_functions, discrepancies, assembly)
- [x] **#3** Define TS + Rust types and dataset loader
- [x] **#4** Build BOM view
- [x] **#5** Build Discrepancy view — red banner for unresolved build-critical, localStorage Resolved toggle
- [x] **#6** Implement Digi-Key CSV export — save-as dialog (Tauri) / Blob download (web) + build-qty multiplier
- [x] **#7** Set up dual-target build — `scripts/bake-dataset.ts`, `npm run build:web` emits dist/ under `/open-book-builder/`
- [x] **#8** Parse KiCad PCB and 2D preview — `lexpr` walker → 27 components + 4 holes + 40 edge segments; `BoardView.tsx` SVG
- [x] **#9** Build 3D BoardViewport — Three.js extruded board (holes punched through), per-component extruded boxes with part-class heights, OrbitControls, raycaster click-select
- [x] **#10** Add hero meshes — 4 procedural Three.js builders (pi-pico, c2-module, keystone-1022, mem2075); gdew042t2 deferred to #11 where it physically belongs
- [ ] **#11** Parse EAGLE C2 driver module — `quick-xml` + serde structs
- [ ] **#12** Build Assembly view — checklist + mini viewport with step-based highlighting
- [ ] **#13** Polish — net coloring, keyboard shortcuts, About screen

Steps 1–7 give a shipable tool (BOM + discrepancies + sourcing + web share)
with no 3D. Steps 8–13 add the visualization half — task #8 is the
parser + a 2D SVG stepping-stone; task #9 upgrades it to Three.js.

## Canonical source files

Read-only inputs (not modified by this project):

- `~/Projects/the-open-book/CONTEXT.md` — unified component catalog, BOM
  reconciliation, discrepancy inventory (seed for the hand-authored JSONs).
- `~/Projects/the-open-book/folder/The-Open-Book-main/OSO-BOOK-C1/` —
  `1-click-bom.csv`, `.kicad_pcb`, `.kicad_sch`.
- `~/Projects/the-open-book/folder/The-Open-Book-main/Fabrication Files/Castellated E-Paper Driver/OSO-BOOK-C2-02 (PCBWay)/` —
  `.brd`, `.sch`, BOM CSV.
- `~/Projects/the-open-book/COGS-LIST` — third-party cost annotations
  (with the known arithmetic error and wrong-board noise).

## License

Code: MIT (to be added; matches dodec-mapper's choice).
Visualization data: derives from upstream CC-BY-SA 4.0 work.
