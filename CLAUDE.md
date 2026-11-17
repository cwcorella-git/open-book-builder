# Claude notes — Open Book Builder

Start here. Layout, tabs and data model are in [README.md](./README.md) — don't
duplicate them in this file. The app is Python + PySide6 (rewritten from
React/Tauri on 2026-11; the old tool lives at git tag `web-tool-final`).

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
- C2: 18 components, 3 holes, 4 edge segments, 153 traces, 21 nets

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
   virtual GDEW042T2 at a fixed position; it isn't in the `.brd`. Removing the
   `Display` line from the C1 BOM silently drops it from the C2 board.
6. **Board coordinates are KiCad's: millimetres, y down.** Components on the
   bottom side use rotation negated and no mirror in the board view (checked
   against trace endpoints). The Bottom view mirrors the whole board.
7. **The app expects a repository checkout.** `data/` is found by walking up
   from the package; a plain `pip install` without the repo has no data.
8. **Review findings.** `docs/hardware-build-review-2026-11-15.md` lists them.
   Fixed 2026-11-17: Pico is SC0915, the 1022C retainer row, circuit
   descriptions, firmware and font steps (marked Untested), C2 internals out of
   the export, display now GDEY042T81 (unvalidated), cost wording. Still open: the
   SC0915 Digi-Key number, C2 inductor/current-sense/pulldown values for the new
   display, a firmware build, the C1 copper comparison, quotes and the pilot.
9. **Planning data is edited in the app and saved to `data/configs.json`**
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
- The display (GDEW042T2) is intentionally sourced only via Good Display; no
  Western distributor. Don't flag it as a gap.
- Parsers in `build/` are ports of the old Rust code. Keep outputs identical to
  the golden file unless a data change is intended.
