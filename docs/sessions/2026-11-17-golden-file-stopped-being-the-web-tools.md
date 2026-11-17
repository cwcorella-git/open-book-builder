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
| 9 | Phase B: PlatformIO build of libros with PRs #10 and #11 | **done** — clean compile, record in `docs/firmware-build-2026-11.md` (not hardware validation), `e7feeb1` |
| 10 | Take the GitHub Pages site down | **done** — operator said to; `gh api -X DELETE .../pages`, site now 404 |
| 12 | Run the old web tool locally until parity | **done** — `scripts/legacy-web.sh` serves the Release build at `localhost:4173/open-book-builder/`; served pages and assets checked with curl, never opened in a browser, `a0fdd4f` |
| 13 | Case view clipping | **done** — `f57709a`. Triangle sorting drew thin wall triangles out of order; now a numpy depth buffer (low resolution while dragging, sharp when still). Checked by eye offscreen only |
| 14 | Loose ends from the build and the C1 check | **done** — `f57709a`. sleep.c, size summary and the 16 Pico pads are explained in section 6 |
| 15 | Parity: About tab | **done** — built later as row 31, `49822e4` |
| 16 | Parity: Assembly step highlights its parts on the Board tab | **done** — built later as row 30, `17124be` |
| 17 | Parity: 3D board view | **done** — built later as row 33, `c285e3c` (CPU depth buffer, boxes for parts, no OpenGL) |
| 18 | Board accuracy: draw copper from the manufacturing Gerbers | **done** — built later as row 32, `269be41` and `2aea2d6` |
| 19 | SC0915 Digi-Key number | **blocked** — on the operator, see Open |
| 20 | Hardware values check, configs 1-3 feature interview, quote drafts | **done** — rows 21 and 24 to 26 |
| 21 | GDEY042T81 / C2 values check | **done** — `docs/gdey-c2-values-check.md`. Topology matches Good Display's reference; no GDR pulldown or footprint for one, 10 µH 0805 inductor against 47 µH 500 mA, 0.47 Ω against 2.2 Ω. Desk research only; nobody has shown the published values working with this panel — `8e16c50` |
| 22 | Case view lag | **done** — `5149b53`. Profiled: the whole frame was a Python loop over triangles on one core (177 of 193 ms, GPU unused, 23 other cores idle). Vectorized: about 40 ms per drag frame for Sprint 5. Measured offscreen; not felt on the real desktop |
| 23 | C2 board accuracy | **done** — see section 8 — `e898a0f` |
| 24 | Interview: what configurations 1-3 are | **done** — the operator dropped configurations (section 9). Rulings in the review's `Rulings, 2026-11-17`; `data/configs.json` is now one `First batch` plan; `5a77ea1` |
| 25 | Reader features spec | **done** — `docs/reader-features-spec.md`, spec only, 15 features, 7 requested and 8 mine; `5a77ea1` — `5a77ea1` |
| 26 | Quote request drafts | **done** — `docs/quote-requests.md` (C1 PCB, C1 assembly routes A/B/C, C2-03 module, comparison table). Nothing sent; the commit that adds it follows this row — `d347442` |
| 27 | Author's formatting guide for the site | **done** — `docs/author-guide.md`; checked against the firmware source, not tried on a reader, not tried by anyone but me — `02d92a5` |
| 28 | Site for collections (preloaded choice, downloads) | **done as a design draft** — `docs/collections-site.md`, six questions for the operator; no site exists — `5b00b77` |
| 29 | Plan: assembly highlights, About tab, Gerber Board view, 3D view, three documents | **done** — all five phases; rows 30 to 36 |
| 30 | Assembly step highlights its parts on the Board tab | **done** — `17124be` |
| 31 | About tab with the corrected ordering guide | **done** — `49822e4` |
| 32 | Gerber-based Board view, C2 on the C2-03 route, order zips in `data/fabrication/` | **done** — see section 10 — `269be41`, `2aea2d6` |
| 33 | 3D board view (CPU depth buffer, no OpenGL) | **done** — see section 11 — `c285e3c` |
| 34 | Markdown profile update | **done** — `docs/markdown-profile.md` now splits stock firmware (pilot) from feature firmware (the nine), adds the `type:` tag, `_STATE` and the stale page-map rule — `65b28bd` |
| 35 | Author's guide | **done** — row 27 |
| 36 | Collections site design | **done** — row 28 |
| 37 | Converter for the Markdown profile (source to reader file, with the rejection report) | **done** — `63e59ed` |
| 38 | Card preparation tool for Linux | **done** — `0473c80` (dry run by default, never formats, never run on a real card) |
| 39 | Real part shapes in the 3D view; copper on the 3D slab | **done** — `78c863e` (silkscreen left out, row 40) |
| 40 | Silkscreen on the 3D slab | **done** — `74b5105` (viewed side only, off by default; 95 ms a drag frame on the C1) |
| 41 | The 3D bottom view renders much darker than the top | **done** — `94011f8` (the light's depth part now follows the camera side) |
| 42 | Record the six collections-site answers | **done** — `56a36eb` |
| 43 | Plain-text reading copy from the converter | **done** — `f7a3dc4` |
| 44 | Localhost mockup of the collections site | **done** — `dea9ee3` |
| 45 | Rebuild `babel.bin` from Unifont | **done** — `9c7c58a` (matches the original except version drift; never loaded by the firmware) |
| 46 | Feed the site's `index.json` manifest to the card tool; fix the zip README being copied as a book | **done** — `c91efe6` |
| 47 | Silkscreen for both sides in 3D, drawn only when the view settles | **done** — `d0e98e3` (drag 48 ms with or without it, settled frame 245 ms) |
| 49 | Look at the site in a headless browser and fix what shows | **done** — `711662a` |
| 48 | License decision for a rebuilt `babel.bin` | **blocked** — on the operator; Unifont is GPL v2 or later with a font embedding exception, and what that means for cards sold on Etsy is a legal question |
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

## 12. The documents were checked against the source, not the device

The profile update, the author's guide and the collections design all state what the reader does from reading libros at `3be5d84` plus PRs #10 and #11. Three claims in them rest on a single reading of the code and are the first things a pilot could overturn: that `.pag` is never rebuilt, that progress is written only on Lock or return home, and that bold is two Shift In codes (the shift state machine in `BabelTypesetter.cpp`). The author's guide's worked example was derived by hand from those rules; no converter exists to check it. The guide was passed through the humanizer checklist; it had no dashes or stock phrases, and the one factual slip it caught was mine (a sentence saying updated works restart from the beginning, which no source supports).

Task-table housekeeping: rows 15 to 18 were written as proposals mid-session and were built later as rows 30 to 33; they now say so.

## 13. The converter made the author guide's example a test, and the 3D view got heavier than I planned

The guide's worked example had been derived by hand (section 12). The converter now reproduces it byte for byte, and a test also checks that the guide still shows that example, so the two cannot drift. The bold rule (two Shift In codes, one Shift Out back to plain) held up in the converter's state machine; it is still read from source, not seen on a device. Edge decisions I made and wrote into the profile: links keep text only, `##` and below become a bold line, a tag containing `;` or `:` is an error.

The card tool refuses a path that is not a mount point, and a disk not marked removable. Built-in SD readers (`mmcblk`) usually report not removable, so the refusal message names `--allow-fixed`. That path is tested against a captured `mountinfo` and a fake `sys` folder only.

For the 3D view, the plan said "draw copper if the count allows". It did: about 10,700 copper triangles at 0.02 mm made the C1 drag take 70 to 160 ms offscreen, so I raised the 3D tolerance to 0.05 mm (about 8,700 triangles in all, 55 to 63 ms a drag frame). The old tool's battery cells overlapped each other (two 10.5 mm cells in a 19 mm holder); the port squeezes them to fit and says so. The Pico's USB (4 mm) and the holder's cells exceed the data's `height3d` (1.5 and 12 mm), so the stacking test now checks each part against its own body. Row 39 also turned "Show copper" on by default, because the same box now drives the 3D copper.

## 14. The original babel.bin was a good oracle, and the answers came from the data, not my guesses

The plan expected the spike to be the risky row. The firmware source fixed the header, the 6-byte table entries and the extras table, and the original file (fetched read-only into the scratchpad, never kept) confirmed every offset. The glyph bytes turned out to be Unifont's hex bytes unchanged. The rest was inference, and each rule was fitted against the original before it went in: the line-break flag is set for exactly the classes B2, BA, HY, ID, SP and SY (my first guess included ZW and was wrong), all Cc and Cf characters count as control (as do U+E000 and U+F8FF), unassigned and private-use code points are left out, and combining marks in right-to-left blocks count as strong right to left. Case mappings had to come from UnicodeData.txt, not Python's `str.upper()`, which returns full mappings the original does not use. After that, over 55,445 shared code points the only differences are glyph shapes from an older Unifont (12,487), 23 widths, one reclassified character and a few added pairs.

Three things I would not have guessed: the original Python I compared under (system 3.12) knows Unicode 15.0 and uv's 3.14 knows 16.0, so the builder refuses data files of another version; the original has a type 64 table the firmware ignores, which the rebuild omits; and the guide's claim that the site would rebuild the file was cheaper than the licensing question it opened (row 48).

The 3D view: the shading bug was a light direction that added from above and subtracted from below (grey 149 against 58). Silkscreen is about 72,000 triangles for the C1 at 0.05 mm, so it draws the viewed side only at 0.2 mm and stays off until asked.

## 15. A test had locked in a bug, and the slow part of the 3D view was not the part I measured

Row 38's card tool took every `.txt` in a collection zip as a work. The site's zips held a `README.txt`, so the tool would have copied it to the card and the reader would have listed it as a book, and `test_load_works_from_folder_zip_and_selection` asserted exactly that set. I only noticed while reading `load_works` to plan the manifest row. The zip's instruction file is now named `README` with no extension (so the reader never lists it, and "copy every .txt file" is true), `README.txt` is skipped anywhere, and the tool checks every package and work against `index.json` before copying.

For silkscreen on both sides I planned around drag-frame cost, and the mask fixed that (the detail triangles are skipped when the frame is a drag, so 80,000 triangles cost the same as 8,700). The slow part was another one: rebuilding the C1 view took 3.8 s, 2.8 s of it in `shapely.simplify`, on every board or side switch. The simplified triangles never change, so they are cached as numpy arrays in `fabrication.layer_triangles` and made by the background warm-up; a rebuild is now about 0.3 s. The first 3D view still waits for the warm-up (a few seconds of background work after launch).

The site mockup was checked in headless Chrome at 390 px and 1000 px wide and with the dark colour tokens forced on (Chrome's own dark-mode flags do not set the colour scheme the page asks for): no overflow, tables and code blocks fit, contrast is fine. One repeated sentence on the card page was removed. Not checked: Firefox, a real phone, print.

## Open

Never verified:
- **The app has never been opened on the real Selkies desktop.** Every screenshot is offscreen Qt. `~/Desktop/open-book-builder.desktop` (Exec `run.sh`) exists and `run.sh` stayed up for 4 s offscreen. If godot-stream manages desktop launchers it may need moving there.
- The firmware compiles with both PRs (`docs/firmware-build-2026-11.md`); nothing was flashed or run on a board, and a clean compile is not hardware validation. The sleep path has never run.
- C2 inductor, current-sense and pulldown values for the GDEY042T81 are unresolved. No ten-panel source exists. No quote, order or pilot.
- C1 copper traces and silkscreen were not compared (pads were, see section 6).
- Prices are Codex's dated 2026-11-15 figures, not refreshed. The spare defaults in `data/configs.json` are my starting proposals.
- Ported since: the About tab, Show on Board, a 3D board view with simple part bodies and copper (rows 37 to 39). Not ported: the old tool's labels and rounded shapes. **None of the Board tab work (Gerber layers, 3D shapes and copper, picking, highlights) has been seen on the real desktop.** The Gerber view's first-draw and repaint times (about 100 ms at fit zoom) and the 3D drag times (55 to 63 ms on the C1) were measured offscreen only.
- **Nothing from rows 37 to 47 has run on a device.** The converter's output, a rebuilt `babel.bin` and the card tool have never touched the firmware or a real card; the localhost site has been fetched with curl and built under test but not looked at in a browser. The 3D silkscreen drag time (95 ms) was measured offscreen.
- **The converter's output has never been loaded by the firmware, and the card tool has never touched a real card.** Both are checked against fixtures and the source reading in the profile.
- The depth-buffered Case view was checked by eye on offscreen renders only; it has not been dragged by hand.
- **SC0915 Digi-Key number:** open https://www.digikey.com/en/products/detail/raspberry-pi/SC0915/13684020 and copy the **Digi-Key Part Number** from the product details table at the top of the page. It should look like `2648-SC0915CT-ND`. Pick the Cut Tape variant (Tape & Reel and Digi-Reel have different numbers), which is the $4.59 listing in the review. Then put it in the `Digikey` column of the U1 row in `data/bom-c1-main.csv`, or tell the next session.

The operator's calls: the SC0915 Digi-Key number; whether and when to send the quote requests; who writes the firmware features; the six questions in `docs/collections-site.md`; the decision register items still open in the review.

## Resume here

Everything in the 2026-11-17 plans is written and pushed except the proposed rows above. Nothing is running in the background.

- **Look at the app first.** It has never been opened on the real Selkies desktop. Open `~/Desktop/open-book-builder.desktop` and try: Assembly > Show on Board, Board with Layers from set both ways, the 2D and 3D views (drag, scroll, click a part), the Case tab (it was laggy before the depth-buffer rewrite), the About tab. Every screenshot so far is offscreen Qt.
- **The operator's calls:** the SC0915 Digi-Key number (link and what to look for are under Open); whether and when to send the quote requests in `docs/quote-requests.md`; who writes the feature firmware (`docs/reader-features-spec.md`, spec only); the six questions in `docs/collections-site.md`; the decision-register items still open in the review.
- **Next rows if asked:** none are proposed. Row 48 (the `babel.bin` license) is the operator's. Rows 37 to 47 and 49 are done.
- **Try the site and the font build:** `uv run python scripts/build_site.py` then `python3 -m http.server -d site/_out --bind 127.0.0.1 8000` and open http://127.0.0.1:8000. For `babel.bin` you need Unifont's hex file and the matching Unicode data files (see `docs/collections-site.md`); `/usr/bin/python3` is Unicode 15.0.
- **Try the new tools:** `uv run python -m open_book_builder.convert tests/fixtures/works -o /tmp/out`, and `python3 scripts/prepare_card.py <mounted card> --works /tmp/out --babel <babel.bin>` (a dry run unless `--write`).

Plain lines: nothing unlanded; `main` is pushed. Pages is off; `./scripts/legacy-web.sh` serves the old tool.

CLOSABLE: every phase of both plans is written, committed and pushed; what is left needs the operator, a real display, or a pilot reader.
