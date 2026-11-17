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
| 9 | Phase B: PlatformIO build of libros with PRs #10 and #11 | **in progress** — clone and merge done, build running when this was written, record doc not written |
| 10 | Take the GitHub Pages site down | **blocked** — on the operator saying the app is good |
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

## Open

Never verified:
- **The app has never been opened on the real Selkies desktop.** Every screenshot is offscreen Qt. `~/Desktop/open-book-builder.desktop` (Exec `run.sh`) exists and `run.sh` stayed up for 4 s offscreen. If godot-stream manages desktop launchers it may need moving there.
- No firmware was built or flashed; the two PRs merge cleanly, nothing more. A clean build will not be hardware validation.
- C2 inductor, current-sense and pulldown values for the GDEY042T81 are unresolved. No ten-panel source exists. No quote, order or pilot.
- C1 copper and silkscreen were not compared; the 16 U1 pad misses are unexplained.
- Prices are Codex's dated 2026-11-15 figures, not refreshed. The spare defaults in `data/configs.json` are my starting proposals.
- The About tab, 3D board view with hero meshes, and the Assembly mini viewport were not ported (they are in the tag).

The operator's calls: when to take Pages down (`gh api -X DELETE repos/cwcorella-git/open-book-builder/pages`, not run); the SC0915 Digi-Key number; configurations 1-3 features and quantities; the decision register items still open in the review.

## Resume here

Pick up row 9 (Phase B).
- Build was started in the background: task id `bsgc7ufla`, log `/tmp/claude-1000/-home-user-Projects-open-book-builder/43b96f7b-b610-4d95-8f83-b78d2695b57a/scratchpad/pio-build.log` (ends with `exit=<code>`; the scratchpad may be cleared by a reboot). Command: `systemd-run --user --scope -p MemoryMax=2500M -p MemorySwapMax=0 timeout -k 10 1500 /data/checkouts/libros-pio/.venv/bin/pio run -e pico` in `/data/checkouts/libros` with `PLATFORMIO_CORE_DIR=/data/checkouts/libros-pio/core`. When it was last read it was still downloading `toolchain-gccarmnoneeabi`; MemAvailable about 3.4 GB.
- If it exited 0: `sha256sum /data/checkouts/libros/.pio/build/pico/firmware.uf2` (or `.bin`/`.elf`, whichever exists), note PlatformIO 6.2.0, `raspberrypi@1.20.0`, libros branch `obb-pilot` at `5196839` (base `3be5d84`, PR #10 `abc2d5f`, PR #11 `a2f91fb`), then write `docs/firmware-build-2026-11.md` (a new file already proposed in the plan), say plainly it is not hardware validation, commit and push.
- If it failed or timed out: record the error text in the same doc and leave the assembly steps Untested.
- Then set the plan file `/home/user/.claude/plans/concurrent-baking-book.md` as done and update the review's "next session" list.

Plain lines: nothing unlanded; `main` is at `a201687` plus this doc. Pages still serves the old site.

HOLDING: Phase B build was still running and nothing about it is verified.
