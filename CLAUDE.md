# Claude notes — Open Book Builder

Start here. Layout, tabs and data model are in [README.md](./README.md) — don't
duplicate them in this file. The app is Python + PySide6 (rewritten from
React/Tauri on 2026-11; the old tool lives at git tag `web-tool-final`; its Pages
site is down, `./scripts/legacy-web.sh` serves the old build locally).

## Canonical commands

```bash
uv venv .venv && uv pip install -e '.[dev]'   # once
uv run open-book-builder                       # run the app
uv run pytest                                  # tests (offscreen Qt, no display needed)
uv run python -m open_book_builder.build.dataset_build out.json   # dump the dataset
```

## UI rules

Follow `~/Desktop/voicebake ui style guide` (copy of the voicebake app's guide):
native Qt widgets only, no stylesheets or hard-coded colors (the board view
takes its colors from the palette), Title Case buttons, state shown as words
with tooltips, an empty-state message on every view, confirmation before
anything destructive, sentence-case messages ending with a period, no emojis.

## Sanity check numbers

`tests/test_build.py` compares the freshly built dataset with
`tests/fixtures/board-dataset.golden.json`. The golden file was regenerated on
purpose on 2026-11-17 after the review corrections (the web tool's original is in
the `web-tool-final` Release). It should hold:

- 24 BOM rows · `perUnitUsd ≈ 32.53` · `missingLineItems == ["OSO-BOOK-C2-01"]` · `unavailableLineItems == ["GDEY042T81"]`
- 13 assembly steps (12 active, 1 deferred)
- C1: 27 components, 4 holes, 40 edge segments, 296 traces, 76 vias
- C2: 18 components, 3 holes, 4 edge segments, 152 traces, 21 nets

If a number drifts, find out why before updating the golden file. Update the
golden file only for an intended data change, in the same commit.

## Silent-breakage traps

1. **The dataset is built from `data/` at every start.** There is no baked JSON
   to refresh. A change to a CSV, `component_functions.json`, `assembly.json`
   or a board file shows on the next launch and in the next test run, and it
   will make the golden comparison fail until the golden file is updated.
2. **Two BOM CSV formats.** C1 is Joey's `1-click-bom.csv` (has `Digikey` /
   `Mouser` columns). C2 is PCBWay PCBA (no distributor columns; depends on
   `component_functions.json` for DK/Mouser/LCSC). The C2 header
   `*Package/Footprint ` has a trailing space; `build/bom.py` accepts both
   spellings. Don't "fix" it.
3. **`_apply_lookup()` in `build/bom.py` is the merge point.** CSV fields win
   over JSON fallbacks for distributor PNs. Missing-MPN lines fall back to the
   CSV description as `function`.
4. **Cost summary deliberately excludes all C2 lines.** The driver module is
   priced as one pre-assembled PCBA (`OSO-BOOK-C2-01`), not part by part. Don't
   sum C2 internals. The C2 CSV lines carry `routeDetail`, which keeps them out of
   the Digi-Key export, the order quantities and the Checklist.
   The first offer in `data/offers.json` sets a part's unit price; a part with no
   offer keeps its undated scalar price and is labelled Estimate. The 32.53 total
   uses a promotional display price with no stock (see `unavailableLineItems`).
5. **C2 has a synthesized `Display` component.** `build/eagle.py` makes a
   virtual GDEY042T81 at a fixed position; it isn't in the `.brd`. Removing the
   `Display` line from the C1 BOM silently drops it from the C2 board.
6. **Board coordinates are KiCad's: millimetres, y down.** Pad positions use the
   component's rotation negated and no mirror, bottom side included. This is
   checked against the C1-05 Gerber flashes (`tests/test_gerber_accuracy.py`):
   every pad matches within 0.02 mm except the Pico's SMD pads, which the Gerbers
   place 0.9 mm further out than the source. A pad's angle in the file includes the
   footprint's, so a quarter-turn relative to the footprint swaps its width and height.
   The C2 comes from EAGLE, which is y up: `build/eagle.py` flips every y to height minus y,
   and for mirrored (bottom) elements it flips pad x and stores the rotation reversed. That is
   the only rule that matches all 59 SMD pads against the C2 Gerbers (also tested).
   The Bottom view mirrors the whole board.
7. **The app expects a repository checkout.** `data/` is found by walking up
   from the package; a plain `pip install` without the repo has no data.
8. **Review findings.** `docs/hardware-build-review-2026-11-15.md` lists them.
   Fixed 2026-11-17: Pico is SC0915, the 1022C retainer row, circuit
   descriptions, firmware and font steps (marked Untested), C2 internals out of
   the export, display now GDEY042T81 (unvalidated), cost wording. Still open: the
   SC0915 Digi-Key number, C2 inductor/current-sense/pulldown values for the new
   display, a firmware build, the C1 copper comparison, quotes and the pilot.
9. **The Board tab draws from the order files by default.** `data/fabrication/` holds
   the C1-05 and C2-03 zips. `build/gerber.py` reads the RS-274X/Excellon subset they use
   (it counts, never guesses, anything else), `build/gerber_geometry.py` merges layers into
   polygons with shapely, and `fabrication.py` maps each board's files and coordinates. The
   layers are read on a background thread at startup (silkscreen is the slow one, about 1.5 s
   each) and the tab shows the design file until they are ready. Paths are simplified by
   0.005 mm (copper) and 0.01 mm (silkscreen) because the silkscreen text is about 200,000
   points. Components, selection and nets still come from the KiCad/EAGLE parsers.
10. **The 3D board view is the same CPU depth buffer as the Case tab** (`meshview.py`),
   with no OpenGL: it works over Selkies and under test. `mesh3d.py` extrudes the outline
   (mounting holes cut out) 1.0 mm and adds a box per component from its pad extents and
   `footprintBbox.height3d`; parts on the bottom hang below the slab. The five parts with a
   `heroMeshId` (Pico, C2 module, battery holder, microSD socket, panel) are several boxes from
   `parts3d.py` (ported from the old tool's `hero-meshes.ts` in `web-tool-final`, without its
   labels; the battery cells are boxes squeezed to fit). Such a part can be taller than its
   `height3d` (the Pico's USB). Copper from the Gerbers is drawn 0.02 mm proud of each face,
   simplified to 0.05 mm, and picks as the slab; it is about 7,000 triangles on the C1, so keep
   an eye on drag time before adding silkscreen. The virtual C2 Display is 95 x 110 mm and
   dwarfs the C2 board, which is true to scale.
11. **Planning data is edited in the app and saved to `data/configs.json`**
   (File > Save). `offers.json`, `checklist.json` and `revisions.json` are edited
   by hand. Keep dated offers dated and mark estimates as estimates.

## Data verification workflow

When BOM pricing or distributor links need updating, the verification pattern
is an interactive HTML page written to `~/Desktop/` (e.g.
`node scripts/build-price-verification.mjs` writes `c1-price-verification.html`).
The page holds the table, lets the user click through to distributors, and
exports the verified state back as an HTML file with localStorage preserved.
Only edit `data/component_functions.json` / `data/bom-c1-main.csv` once the user
confirms.

## Conventions

- Commits: terse imperative subject, no emoji, under ~70 chars, details in the
  body. End with the `Co-Authored-By` line for the model that wrote the commit.
  Commit to `main` and push over HTTPS with the `gh` credential helper (the
  workstation's SSH deploy key cannot push).
- Don't create new `.md` files unless the user asks. If a topic warrants
  persistent documentation, propose it first.
- Prefer editing existing tabs over introducing new abstractions.
- The display (GDEY042T81) is intentionally sourced only via Good Display; no
  Western distributor. Don't flag it as a gap.
- Parsers in `build/` are ports of the old Rust code. Keep outputs identical to
  the golden file unless a data change is intended.
