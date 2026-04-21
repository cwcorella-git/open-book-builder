# Claude notes — Open Book Builder

Start here. Architecture, file tree, and tech-stack details live in
[README.md](./README.md) — don't duplicate them in this file.

## Canonical commands

```bash
npm run tauri dev            # desktop dev
npm run bake-dataset         # re-emit public/board-dataset.json (required after data edits)
npx tsc --noEmit             # frontend typecheck
cd src-tauri && cargo check  # backend typecheck
npm run build:web            # full web build (bake + tsc + vite build)
```

## Sanity check numbers

After `npm run bake-dataset`, `public/board-dataset.json` should have:

- 23 BOM rows · `costSummary.perUnitUsd ≈ 43.27` · `missingLineItems == ["OSO-BOOK-C2-01"]`
- 13 assembly steps
- C1: 27 components, 4 holes, 40 edge segments, 296 traces, 76 vias
- C2: 18 components, 3 holes, 4 edge segments, 153 traces, 21 nets

If any of these drift, investigate before assuming the dataset is fine.

## Silent-breakage traps

Things that would mislead you if you didn't know them:

1. **Static data is `include_str!`'d into the Rust binary.** Editing
   anything in `src-tauri/data/` (CSVs, JSON, `.kicad_pcb`, `.brd`)
   requires a Rust rebuild + `bake-dataset` before the web target sees
   the change. `npm run tauri dev` and `npm run build:web` both handle
   this; ad-hoc edits do not.

2. **Rust ↔ TS type mirroring is manual.** `src-tauri/src/types.rs`
   (serde `rename_all = "camelCase"`) and `src/lib/types.ts` must be
   edited together. New optional fields need `#[serde(skip_serializing_if = "Option::is_none", default)]`
   on the Rust side.

3. **Two BOM CSV formats.** C1 is Joey's `1-click-bom.csv` (has
   `Digikey` / `Mouser` columns). C2 is PCBWay PCBA (no distributor
   columns; depends on `component_functions.json` for DK/Mouser/LCSC).
   The C2 header `*Package/Footprint ` has a trailing space — the
   parser keeps both as alias. Don't "fix" it.

4. **`apply_lookup()` in `bom.rs` is the merge point.** CSV fields win
   over JSON fallbacks for distributor PNs. Missing-MPN lines fall back
   to the CSV description as `function`.

5. **Cost summary deliberately excludes all C2 lines** — the driver
   module is priced as a single pre-assembled PCBA (`OSO-BOOK-C2-01`),
   not component-by-component. Don't sum C2 internals.

6. **C2 has a synthesized `Display` component.** `eagle.rs` fabricates
   a virtual GDEW042T2 at a fixed position; it isn't in the `.brd`.
   Removing the `Display` line from the C1 BOM silently breaks C2
   rendering.

7. **`public/board-dataset.json` is gitignored.** It's a build artifact.
   The GitHub Pages workflow regenerates it.

8. **Base path `/open-book-builder/`** is baked into the web build via
   `package.json`'s `build:web` script. Forks must update it.

## Data verification workflow

When BOM pricing or distributor links need updating, the verification
pattern is an interactive HTML tool written to `~/Desktop/` (e.g.
`c2-price-verification.html`). The tool holds the table, lets the user
click through to distributors, and exports the verified state back as
an HTML file with localStorage preserved. Only edit the canonical
`component_functions.json` / `bom-c1-main.csv` once the user confirms.

## Conventions

- Commits: terse imperative subject, no emoji, sign off with
  `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`. Keep
  subject under ~70 chars; details in body.
- Don't create new `.md` files unless the user asks. If a topic
  warrants persistent documentation, propose it first.
- Prefer editing existing components over introducing new abstractions.
  `SourceLinks` / `DistributorLink` / `Field` are the shared UI atoms
  across `BoardView` and `BomView` — reuse them.
- The display (GDEW042T2) is intentionally sourced only via Good
  Display; no Western distributor. Don't flag it as a gap.
