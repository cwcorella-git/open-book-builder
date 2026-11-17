# Open Book Builder

A desktop app for looking at, checking and sourcing
[The Open Book](https://github.com/joeycastillo/The-Open-Book), Joey
Castillo's open-source e-reader (Raspberry Pi Pico, 4.2" black and white
e-paper, two AAA cells, CC-BY-SA 4.0).

The app is written in Python with PySide6 and uses the platform's native
Qt look. It follows the voicebake desktop style guide: system theme, no
stylesheets, states shown as words, a tooltip on every non-obvious control.

The earlier React/Tauri tool and its GitHub Pages site are retired. They are
kept at the git tag `web-tool-final`, and the Release of the same name holds
the built site and the dataset it produced.

## Hardware review and continuation

Before using the app to order parts, read the [2026-11-15 hardware and build review](docs/hardware-build-review-2026-11-15.md). It records confirmed BOM and assembly-instruction errors, requirements for ten US builds, pricing limits, and outstanding validation. The BOM, circuit notes, assembly steps and cost view now reflect those findings (2026-11-17); the review lists what is still open. The [session record](docs/session-2026-11-15.md) summarizes decisions; use the [continuation handoff](docs/handoff-2026-11-15.md) when resuming work.

## Run it

```bash
uv venv .venv && uv pip install -e '.[dev]'   # once
uv run open-book-builder                       # start the app (or ./run.sh)
uv run pytest                                  # tests
```

## Tabs

- **BOM**: 24 lines across both boards, with a board filter, a readers
  multiplier, an optional-parts toggle, editable spare counts, order
  quantities, dated prices with their basis (Listed, Estimate) and a Digi-Key
  BOM Manager CSV export. The C2 driver is one module line; its internal parts
  are hidden unless you ask, and never exported.
- **Checklist**: everything to buy or arrange for one of three configurations
  (they share one PCB; features and quantities are not defined yet): parts with
  order quantities, boards and assembly, cards and batteries, fees, and one-time
  tools kept apart. Open items stay marked Open until there is a price or quote.
- **Assembly**: 13 build steps (12 active, the case step is deferred). Steps
  rewritten after the review are marked Untested. Progress is saved on this
  computer.
- **Board**: 2D view of the C1 main board (from KiCad) and the C2 driver
  (from EAGLE): outline, holes, copper traces, vias, silkscreen and
  components. Select a component to see its part. The bottom view is mirrored.
- **Case**: rotatable view of the Sprint 5 and minimal case STL models, with
  a Save Files action.

Not carried over from the web tool: the About tab (ordering guide and project
status), the 3D board view with hero meshes, and the mini viewport in the
Assembly tab. They are in the `web-tool-final` tag.

## Layout

```
pyproject.toml            package metadata, entry point open-book-builder
src/open_book_builder/
  app.py, window.py       entry point and main window
  bom_tab.py, assembly_tab.py, board_tab.py, case_tab.py
  dataset.py              Dataset, BomLine, AssemblyStep; builds from data/ at startup
  digikey_csv.py          Digi-Key CSV export
  geometry.py             arc helper for the board view
  build/                  parsers: bom, kicad_pcb (C1), eagle (C2), net_category, footprint_heights
data/                     source files: BOM CSVs, component_functions.json, assembly.json,
                          OSO-BOOK-C1.kicad_pcb, OSO-BOOK-C2-02.brd, case/ (STL, SCAD)
                          planning data: offers.json (dated prices), configs.json (configurations,
                          spares), checklist.json (non-BOM items), revisions.json (pinned upstream files)
tests/                    pytest; fixtures/board-dataset.golden.json is the expected dataset
scripts/                  build-price-verification.mjs (Node, writes a price check page to ~/Desktop)
reference/                upstream Open Book sources and notes
docs/                     hardware review, session record, handoff
```

## Data

`data/` holds the only copy of the source data. The app builds the dataset
from it every time it starts (about 0.3 s), so edits show up on the next
launch. To write the dataset as JSON:
`uv run python -m open_book_builder.build.dataset_build out.json`.

The dataset has `boards` (per-board components, outline, nets, traces, vias),
`bom`, `assembly` and `costSummary`. The cost summary counts non-optional C1
lines only. C2 internals are left out because the driver module is priced as
one pre-assembled unit. Prices come from `data/offers.json` (dated listings);
parts without an offer keep an undated estimate. Lines whose offer shows no
stock are named in `unavailableLineItems`.

### Sanity check

`tests/test_build.py` rebuilds the dataset and compares it to the golden file (regenerated on purpose on 2026-11-17 after the review corrections; the web tool's original output is in the `web-tool-final` Release).
The expected values:

- 24 BOM rows, `perUnitUsd` 32.53, `missingLineItems == ["OSO-BOOK-C2-01"]`, `unavailableLineItems == ["GDEY042T81"]`
- 13 assembly steps
- C1: 27 components, 4 holes, 40 edge segments, 296 traces, 76 vias
- C2: 18 components (17 from the board file plus a synthesized Display),
  3 holes, 4 edge segments, 153 traces, 21 nets

## Upstream source files

Read-only inputs, not modified by this project:

- `The-Open-Book/OSO-BOOK-C1/`: `1-click-bom.csv`, `.kicad_pcb`, `.kicad_sch`
- `The-Open-Book/Fabrication Files/Castellated E-Paper Driver/OSO-BOOK-C2-02 (PCBWay)/`:
  `.brd`, `.sch`, BOM CSV

## License

Code: MIT. Board and case data derive from the upstream
[CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) work.
