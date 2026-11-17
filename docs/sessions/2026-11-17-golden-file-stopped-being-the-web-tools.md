# 2026-11-17 — the golden file stopped being the web tool's the moment the review was applied

Started as "review what Codex did", became: retire the web/Tauri tool for a PySide6 desktop app, then apply Codex's findings to the new app's data. Repo: `open-book-builder`, branch `main`, all pushed over HTTPS with the `gh` helper (the workstation's SSH deploy key cannot push).

| # | item | state |
|---|---|---|
| 1 | Review Codex's work (docs only, no code) | **done** — claims spot-checked against `data/` and `src-tauri`; all held. Docs committed `4309cc5` |
| 2 | Preserve the web tool | **done** — tag `web-tool-final` (`4309cc5`) and Release of the same name (site zip + baked dataset) |
| 3 | PySide6 app: BOM, Assembly, Board, Case tabs | **done** — `6b44c05`, `325510c`, `0bab2d8`, parsers `2898427` |
| 4 | Replace web/Tauri files at repo root, build data from `data/` at startup | **done** — `abb46da`, reword `b0fe0e4` |
| 5 | Phase A0: compare C1-05 zip and C2-02/03 against the viewer data | **done** — findings in `data/revisions.json` |
| 6 | Phase A: data corrections, offers/configs/checklist, Checklist tab, Untested/Deferred steps | **done** — `5958788`, `4274817`, `981c8a6` |
| 7 | Phase C: C1 placement file + assembly BOM + notes | **done** — `40661e8` |
| 8 | Phase D: Markdown profile spec | **done** — `71a966b`, fix `a201687` |
| 9 | Phase B: PlatformIO build of libros with PRs #10 and #11 | **done** — clean compile, record in `docs/firmware-build-2026-11.md` (not hardware validation) |
| 10 | Take the GitHub Pages site down | **done** — operator said to; `gh api -X DELETE .../pages`, site now 404 |
| 12 | Run the old web tool locally until parity | **done** — `scripts/legacy-web.sh` serves the Release build at `localhost:4173/open-book-builder/`; served pages and assets checked with curl, never opened in a browser |
| 13 | Case view clipping | **done** — `f57709a`. Triangle sorting drew thin wall triangles out of order; now a numpy depth buffer (low resolution while dragging, sharp when still). Checked by eye offscreen only |
| 14 | Loose ends from the build and the C1 check | **done** — `f57709a`. sleep.c, size summary and the 16 Pico pads are explained in section 6 |
| 15 | Parity: About tab | **proposed** — ordering guide (Gerber files, PCB specs, display sourcing), project status and credits, rewritten from the old `AboutView.tsx` (tag `web-tool-final`) with the review's corrections: C1-05 zip has no placement file, C2-03 route, GDEY unvalidated, no "$30–80" |
| 16 | Parity: Assembly step highlights its parts on the Board tab | **proposed** — selecting a step switches the Board tab to the right board and side and highlights `componentRefs`. Replaces the old 3D mini viewport |
| 17 | Parity: 3D board view | **proposed** — orbit view of both boards with component bodies (`footprintBbox.height3d` is already in the data; the old tool used three.js and hero meshes for the Pico, C2, holder, microSD and panel). Needs Qt3D or an OpenGL widget. The largest item |
| 18 | Board accuracy: draw copper from the manufacturing Gerbers | **proposed** — see section 7 |
| 19 | SC0915 Digi-Key number | **blocked** — on the operator, see Open |
| 20 | Hardware values check, configs 1-3 feature interview, quote drafts | **done** — rows 21 and 24 to 26 |
| 21 | GDEY042T81 / C2 values check | **done** — `docs/gdey-c2-values-check.md`. Topology matches Good Display's reference; no GDR pulldown or footprint for one, 10 µH 0805 inductor against 47 µH 500 mA, 0.47 Ω against 2.2 Ω. Desk research only; nobody has shown the published values working with this panel |
| 22 | Case view lag | **done** — `5149b53`. Profiled: the whole frame was a Python loop over triangles on one core (177 of 193 ms, GPU unused, 23 other cores idle). Vectorized: about 40 ms per drag frame for Sprint 5. Measured offscreen; not felt on the real desktop |
| 23 | C2 board accuracy | **done** — see section 8 |
| 24 | Interview: what configurations 1-3 are | **done** — the operator dropped configurations (section 9). Rulings in the review's `Rulings, 2026-11-17`; `data/configs.json` is now one `First batch` plan; `5a77ea1` |
| 25 | Reader features spec | **done** — `docs/reader-features-spec.md`, spec only, 15 features, 7 requested and 8 mine; `5a77ea1` |
| 26 | Quote request drafts | **done** — `docs/quote-requests.md` (C1 PCB, C1 assembly routes A/B/C, C2-03 module, comparison table). Nothing sent; the commit that adds it follows this row |
| 27 | Author's formatting guide for the site | **proposed** — not written. Rules are in `docs/markdown-profile.md`, which also needs the `type:` tag, `_STATE` and stale-page-map additions if the features go ahead |
| 28 | Site for collections (preloaded choice, downloads) | **proposed** — the operator's plan; no design yet |
| 29 | Plan: assembly highlights, About tab, Gerber Board view, 3D view, three documents | **in progress** — phases 1 to 4 done, phase 5 (three documents) next |
| 30 | Assembly step highlights its parts on the Board tab | **done** — `17124be` |
| 31 | About tab with the corrected ordering guide | **done** — `49822e4` |
| 32 | Gerber-based Board view, C2 on the C2-03 route, order zips in `data/fabrication/` | **done** — see section 10 |
| 33 | 3D board view (CPU depth buffer, no OpenGL) | **done** — see section 11 |
| 11 | SC0915 Digi-Key part number into `data/bom-c1-main.csv` | **blocked** — on the operator pasting it (Digi-Key returns 403 to the shell) |

## 1. Codex's review held up, and the cheap checks were enough

Every claim I checked reproduced from the repo: SC0918 listed as equivalent to SC0915, no 1022C BOM row, C2 internals exported (90 / 10 / 10 for ten readers), the two contradictory "$30–80" strings, `OSO-BOOK-C1-06` in the embedded board, wrong Q1/Q2 and R3/R4 text, the $180.92 arithmetic. The external claims (prices, stock, PR states) I did not re-check except that libros `main` is `3be5d84` and the PR heads are `abc2d5f` and `a2f91fb`, as the review said.

## 2. The C1 revision question had a boring answer

Believed: the viewer might show a different board from the one the app tells you to order. Evidence: the embedded `.kicad_pcb` is byte-identical to upstream main's and is labelled C1-06 in silkscreen; the C1-05 Gerbers match it on outline, the four 2.5 mm mounting holes and every drill diameter and count (126 plated, 9 not); 190 of 206 pad centers coincide with copper features. The 16 misses are all Pico (U1) pads, probably drawn regions, not looked into further. Copper traces and silkscreen were never compared. C2-02 and C2-03 differ only by a (0.254, 5.08) mm shift and R1's package.

## 3. The rewrite reproduced the web tool exactly, then the review changed the numbers on purpose

The Python parsers (`src/open_book_builder/build/`) matched the Rust output field for field (f32 tolerance 1e-3), including the 23 BOM rows, $43.27, 296 / 76 and 153 / 21 geometry counts. That golden file is now regenerated: 24 rows, $32.53, `unavailableLineItems == ["GDEY042T81"]`. The drop is almost all the display price ($26.90 undated estimate → $14.44 promotional listing with zero stock). The headline got cheaper because the data got more honest, and the cost footer says so. The web tool's original output survives only in the `web-tool-final` Release.

## 4. Things I was told that were wrong or stale

- The old `GDEW042T2` note said GDEY042T81 was "confirmed drop-in compatible by community testers". The creator's own 2023 issue #77 says it may need a larger inductor, a pulldown and a different sense resistor. Rewritten as unvalidated.
- Project `CLAUDE.md` told commits to sign off as "Claude Opus 4.7". I rewrote that line to name the model that wrote the commit; these commits say Sonnet 5.5.
- My memory note said the Sprint 5 case outline fits the C1; Codex said fit was unestablished. The case blurb now says the 88.6 x 118.6 mm size matches the C1 outline and fit around the parts is untested.
- The CSS-free claim "any SD capacity works" had no source. Removed.

## 5. What the libros source says that the 2022 guide did not

Identity is a hash of the file *name*; `.pag` is never invalidated (existence check only); progress is saved only on Lock or return home; favorites do not exist (`flags` unused); `GNRE` is stored but nothing filters on it; the front-matter parser has no bounds checks. All in `docs/markdown-profile.md`, read from source, not seen on a device.

## 6. The three loose ends were not the bugs they looked like

- **sleep.c:** PR #10 removed `#include "pico/stdlib.h"`, which is why three functions are undeclared in `src/platform/pico/sleep.c`. All three are declared in the mbed framework's headers and present in the ELF, and `OpenBookDevice::sleep()` really does call them (rosc, dormant until pin 12). On ARM32 the undeclared calls behave as declared. A warning, not a known fault; the clean fix is two includes. Never run on hardware.
- **Size summary:** PlatformIO's `Flash: 4586 bytes` is wrong. `arm-none-eabi-size` gives 311,344 bytes of code, matching the 311,988 byte `.bin`.
- **The 16 Pico pad misses were a real revision difference.** My first guess ("drawn as regions") was wrong. The C1-05 Gerbers flash the Pico's 40 edge pads and 3 debug pads exactly 0.9 mm further out than the C1-06-labelled source (x for pads 1-40, y for 41-43). Every other pad, 159 checks, lands within 0.02 mm. So the revision label is not just a label: the Pico footprint changed. `tests/test_gerber_accuracy.py` pins both facts. The same check showed the viewer was drawing three Pico pads and two C2 pads with width and height swapped; that is fixed.

## 7. How to make the Board tab more accurate

The pad positions are now measured against the fabrication data, which they were not before. What is still approximate, from most to least valuable:

1. **Draw the copper from the Gerbers, not the source.** The Gerbers are what the maker builds. They would show the C1-05 Pico pads, true trace widths, pad shapes and zones, and would stop the viewer depending on which source revision is checked in. KiCad Gerbers use a small RS-274X subset (round, rectangle and obround apertures, flashes and draws, G36/G37 regions, arcs, dark and clear polarity), so a reader is about 150 lines. Keep the source files for component identity and nets. C1-05 is in `reference/`; the C2-03 fabrication zip is too.
2. **Parse what the source parsers skip:** copper zones and pours (the C2 ground fills), arc tracks, rounded-rectangle corner radii, drill holes drawn in through-hole pads, solder mask openings.
3. **Silkscreen text** (reference designators and notes) and fab-layer outlines, which neither parser reads.
4. **A second check against the order package for C2**, as the C1 test does.
5. **3D (row 17).**

## 8. The C2 view was drawn wrong in three ways, and now a test says so

The operator said the C2 driver "isn't accurate enough yet". Checked against the pad flashes in the C2-02 order Gerbers (`copper_bottom.gbr`), the viewer's rule for bottom parts put 2 of 59 SMD pads in the wrong place (57 of 59 matched), and the board was drawn upside down:

- EAGLE and the Gerbers are y up; the viewer draws y down, so the whole C2 was vertically mirrored.
- For mirrored (bottom) elements the pad x must be flipped and the rotation reversed. Without it, asymmetric parts (the FPC connector, the SOT-23, the diodes) had pads on the wrong side. Symmetric 0805 capacitors hid the error.
- The body box was centred on the component origin, which is wrong for the FPC and the Pico; it now follows the pad extents.

All 59 now land within 0.02 mm (`tests/test_gerber_accuracy.py`). The silkscreen of mirrored C2 parts used the same wrong rotation and now uses the corrected transform, but silkscreen was not compared with the Gerbers. Golden file regenerated on purpose.

## 9. "Don't make any configurations"

The plan assumed three product configurations sharing one PCB, and the interview was about what made them differ. Round 1 answers (all four of hardware, firmware, books and box could differ) and round 2 answers (identical hardware, full firmware on all three, same box) left nothing to tell them apart except books, and the operator then dropped the idea: one build, buyers choose preloaded collections, more downloads from the official site, guides for formatting text. The 2026-11-15 "versions 1, 2, 3" rulings are superseded by a dated block in the review, not edited. The app's three placeholder configurations became one `First batch` plan (10 readers, no expansion), the Checklist's combo box still exists but has one entry.

Two things the interview surfaced that were not obvious from the review: the pilot must run stock firmware while the nine run the new feature set, so the new firmware is a project in its own right (`docs/reader-features-spec.md`); and with no J1-J3 fitted anywhere, hardware population no longer varies at all.

## 10. The Board tab now draws the boards as made

New Gerber and Excellon reader (`build/gerber.py`, tested on synthetic files and on every C1 and C2 layer: nothing unsupported), shapely to merge each layer into polygons, and a **Layers from** choice on the Board tab (Fabrication files by default, Design file as the alternative). The C2 viewer data moved from C2-02 to C2-03 so it follows the chosen route (same parts and nets, shifted by 0.254 mm in x and 5.08 mm in y, 0402 R1, 152 traces against 153); the virtual display kept its place relative to the board corner.

What the Gerbers show that the design file never did: the real silkscreen text (the C1's top side carries the whole build guide, printed on the board), copper pours, true pad shapes and trace widths, the castellated holes on the C2, and the Pico's pads 0.9 mm further out. Startup stayed fast because layers are read on a background thread (window ready in 0.27 s; reading them synchronously had made it 2 s). A full repaint at fit zoom is about 100 ms after simplifying the polygons; panning repaints less than that. Measured offscreen, never felt by hand.

Silkscreen vertex count was the cost: about 200,000 points on a C1 layer, 1.5 s to merge and 177 ms to paint. Simplifying by 0.01 mm keeps 98.7 percent of the area with a third of the points.

## 11. The 3D view reused the case view's depth buffer

`MeshWidget` and `rasterize` moved to `meshview.py` and gained per-triangle colors, a group number per triangle and click picking (the rasterizer now returns a triangle-index image, which is also what picking reads). `mesh3d.py` builds a board in a few milliseconds: the outline polygon (closed with a 0.001 mm snap, because f32 rounding leaves gaps between segments), constrained Delaunay triangulation from shapely for the faces, walls, and a box per component. About 960 triangles for the C1, 530 for the C2. A frame is about 0.2 s when sharp and cheaper while dragging. Clicking a part highlights it with the palette's highlight color and fills the detail pane, as in 2D.

Not done: real part shapes (the old tool's hero meshes), copper or silkscreen on the 3D slab, and any OpenGL path. The Side choice sets which side the camera starts on.

One unexplained stall: a single command that ran the test suite and a screenshot script together timed out at 120 s. The suite alone (three runs), the screenshot script alone (five runs) and the pieces separately all finished normally, so it was not reproduced. Worth knowing if the app ever hangs on exit: the background layer reader is a daemon thread.

## Open

Never verified:
- **The app has never been opened on the real Selkies desktop.** Every screenshot is offscreen Qt. `~/Desktop/open-book-builder.desktop` (Exec `run.sh`) exists and `run.sh` stayed up for 4 s offscreen. If godot-stream manages desktop launchers it may need moving there.
- No firmware was built or flashed; the two PRs merge cleanly, nothing more. A clean build will not be hardware validation.
- C2 inductor, current-sense and pulldown values for the GDEY042T81 are unresolved. No ten-panel source exists. No quote, order or pilot.
- C1 copper traces and silkscreen were not compared (pads were, see section 6).
- Prices are Codex's dated 2026-11-15 figures, not refreshed. The spare defaults in `data/configs.json` are my starting proposals.
- The About tab, 3D board view with hero meshes, and the Assembly mini viewport were not ported (they are in the tag): rows 15 to 17.
- The depth-buffered Case view was checked by eye on offscreen renders only; it has not been dragged by hand.
- **SC0915 Digi-Key number:** open https://www.digikey.com/en/products/detail/raspberry-pi/SC0915/13684020 and copy the **Digi-Key Part Number** from the product details table at the top of the page. It should look like `2648-SC0915CT-ND`. Pick the Cut Tape variant (Tape & Reel and Digi-Reel have different numbers), which is the $4.59 listing in the review. Then put it in the `Digikey` column of the U1 row in `data/bom-c1-main.csv`, or tell the next session.

The operator's calls: the SC0915 Digi-Key number; whether and when to send the quote requests; who writes the firmware features; which parity port comes first; the decision register items still open in the review.

## Resume here

Phase B finished after the first version of this doc was written (the background build reported success; see `docs/firmware-build-2026-11.md` for hashes, versions and the warnings worth a look). Nothing is running in the background now.

- Every plan phase (A0, A, B, C, D) is written. What remains is the operator's: the Pages takedown (done after the first version of this doc: Pages is off), the SC0915 Digi-Key number, configurations 1-3, the open decision-register items, the quotes and a pilot.
- Loose end worth reading first: the `sleep.c` implicit-declaration warnings after PR #10, and the PlatformIO size summary (4.6 KB reported against a 312 KB `.bin`).

Plain lines: nothing unlanded; Pages is off.

CLOSABLE: all planned phases are written and committed; what is left needs the operator or a physical pilot.
