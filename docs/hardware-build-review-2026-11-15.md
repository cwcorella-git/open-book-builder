# Hardware and Build Review — 2026-11-15

## Scope and conclusion

The intended first batch is **ten units, delivered to the United States**. The user has no 3D printer and explicitly deferred cases. They have a basic soldering iron and hand tools, but no multimeter. Map the build and correct the factual foundation before choosing additional features.

Published Open Book board designs provide starting points, but the application is not yet a dependable purchasing or assembly checklist. This review examined repository data, PCB connections, pricing/export logic, upstream fabrication files, firmware changes, and supplier listings. It did **not** validate a physical build, compile the firmware, obtain fabrication quotes, or complete supplier carts. No canonical data or application code was changed.

Status terms:

- **Confirmed:** directly supported by inspected files or the cited source at review time.
- **Proposed:** a recommended build or workflow choice, not a user-approved purchase or tested configuration.
- **Open:** requires further evidence, a quote, or physical validation.

## Confirmed findings

### 1. Original Pico and Pico W are conflated

`src-tauri/data/bom-c1-main.csv` identifies U1 as SC0918 and exports Digi-Key 2648-SC0918CT-ND. `component_functions.json` claims SC0918 and SC0915 are equivalent distributor SKUs and assigns $4.00.

SC0918 is **Pico W**; SC0915 is the **original Pico**. Use original Pico SC0915 for the proposed baseline. Pico W compatibility has not been established by this review; do not describe it as interchangeable.

Sources: [SC0918](https://www.digikey.com/en/products/detail/raspberry-pi/SC0918/16627943), [SC0915](https://www.digikey.com/en/products/detail/raspberry-pi/SC0915/13684020).

**Options check on 2026-11-15:** Digi-Key's direct listings showed original Pico SC0915 at **$4.59** with roughly **39,000** in stock, and Pico W SC0918 at **$7.65** with **6,268** in stock, before US shipping, tax, or possible tariffs. Both clear a ten-piece availability screen at that moment; recheck before ordering. Raspberry Pi's [Pico-series documentation](https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html) identifies Pico W as a wireless RP2040 variant with internal radio pin sharing. The existing libros `platformio.ini` selects `board = pico`; it does not establish a Pico W build or wireless application support. Keep SC0915 as the low-change reference and SC0918 as an investigated option. Pico 2 uses RP2350 and also needs a separate firmware-port check, so its mere stock or similar shape does not make it a supported swap.

### 2. Firmware and font-loading instructions are inaccurate

`src-tauri/data/assembly.json` says to build libros with the Pico SDK. Upstream `platformio.ini` defines a PlatformIO environment named `pico`, with `platform = raspberrypi`, `board = pico`, `framework = arduino`, and `upload_protocol = picotool`. The relevant build command is `platformio run -e pico`; this review did not run it.

The GitHub API confirmed both PRs were open and unmerged:

| Change | Purpose | Observed head commit |
| --- | --- | --- |
| [libros PR #10](https://github.com/joeycastillo/libros/pull/10) | Removes problematic `pico/stdlib.h` includes to address a reported Pico build failure | `abc2d5fd4de4d4a4cb5e1a5e14884201fcab6b5d` |
| [libros PR #11](https://github.com/joeycastillo/libros/pull/11) | Runtime selection between IL0398 and SSD1683 display drivers | `a2f91fb871ad04ce62ec3c1193732b39564851a4` |

Both API responses reported base commit `3be5d8476d2563dfe11920784e98b35e4728a910`. PR #10 changes `src/platform/pico/sleep.c` and `stdlib.c`. PR #11 changes display drivers, hardware initialization, tasks, and main. Its stated detection method reads busy-pin polarity after reset. Its author describes hardware support; this is not our own validation of the combined patches or firmware.

The app's font step describes a bootloader flash utility. The upstream Pico instructions instead say to **put `babel.bin` on the microSD card**; firmware copies it into the external flash on first boot. SD preparation must precede that step. Do not confuse this with the ESP32-specific `esptool.py` instructions in the libros README.

Sources: [PlatformIO configuration](https://github.com/joeycastillo/libros/blob/main/platformio.ini), [Pico setup and font instructions](https://www.oddlyspecificobjects.com/projects/openbook/). The latter is historical documentation, explicitly describing the project's November 2022 state.

**Display hardware caveat found during the decision review:** In [upstream issue #77](https://github.com/joeycastillo/The-Open-Book/issues/77), the project creator said in November 2023 that GDEY042T81 might require a larger C2 inductor, a signal pulldown, and possibly a different current-sense resistor. He said the footprints existed but had not published tested replacement values. Another contributor reported compatibility in their own tests, while a later builder reported SPI integration difficulties. These reports do not establish a repeatable C2 BOM.

The manufacturer-authored [GDEY042T81 specification, reference circuit on page 31](https://files.seeedstudio.com/wiki/Other_Display/42-epaper/GDEY042T81.pdf) shows **47 µH**, a **2.2 Ω** current-sense resistor, and a **1 MΩ** GDR gate pulldown. The published C2-02 and C2-03 BOMs list **10 µH** and **0.47 Ω**, with no matching pulldown. The embedded C2-02 board's element list contains only R1; the pinned C2-03 [fabrication archive](https://raw.githubusercontent.com/joeycastillo/The-Open-Book/6bb483f92e58f4b75d8fcfc72c7c8022f19fe40b/Fabrication%20Files/Castellated%20E-Paper%20Driver/OSO-BOOK-C2-03%20%28JLCPCB%29/OSO-BOOK-C2-03.zip) likewise includes an assembly part list with only R1. A dedicated pulldown footprint is not established in either checked revision despite the creator's earlier general comment. Their component set and reference circuit also differ elsewhere, so these figures are a comparison target, **not instructions to replace three parts in the existing layout**. Check the latest Good Display specification and the C2 nets/footprints; then validate one assembled pilot before assigning this panel to a ten-unit PCBA order.

### 3. Purchasing export mixes assembly routes and omits the retainer

The 1022C battery retainer has a metadata entry and an assembly instruction, but **no C1 BOM row**. `bom::load_all()` constructs rows from CSVs, so a lookup entry alone does not put the retainer in the dataset, cost summary, or export.

`src/lib/digikey-csv.ts` exports every eligible row with a Digi-Key number, without filtering the board. Its comment assumes all C2 rows lack numbers; metadata additions invalidated that assumption. With ten units, the export includes these C2 internals:

| C2 part | Quantity exported |
| --- | ---: |
| CL21B105KBFNNNE, 1 µF capacitors | 90 |
| CL21A475KAQNNNE, 4.7 µF capacitors | 10 |
| IRLML0100TRPBF MOSFET | 10 |

Those are redundant when buying complete C2 PCBA modules. A hand-assembly route would require the complete C2 BOM, not just the subset with Digi-Key numbers. The future purchasing model should explicitly distinguish complete modules from their internal components.

### 4. Cost presentation is incomplete and inconsistent

The stored non-optional C1 subtotal is **$43.27 per device**, including a $26.90 display but excluding unpriced C2 assembly. `src-tauri/src/bom.rs::summarize_cost` intentionally excludes C2 internal rows and all optional rows.

Missing from that subtotal: C1 bare boards, C2 PCBA, 1022C retainers, cards, batteries, consumables, spares, shipping, tax, and tools. The UI shows the same subtotal when optional rows are enabled. The C2 exclusion text is only rendered at the wide breakpoint.

`BomView.tsx` says C2 is $30–80 **for ten boards**; `AboutView.tsx` and metadata say $30–80 **per unit**. Neither has a saved quote. Treat both as unsupported estimates.

Prices lack per-offer dates, quantities, stock evidence, and provenance. `live_price` is initialized to `None`; the name does not mean live prices are fetched. Component metadata `notes` are deserialized but not copied into `BomLine`, so useful qualifications there do not automatically appear in the UI.

### 5. Hardware descriptions disagree with PCB nets

Inspection of `src-tauri/data/OSO-BOOK-C1.kicad_pcb` established the following connections. These are file-level facts, not measured electrical behavior:

| Part | Observed connections | Correction needed |
| --- | --- | --- |
| Q1 | Gate VBUS; source VCC; drain +BATT | Description incorrectly assigns GPIO18 and peripheral switching; this device is in the battery/power path |
| Q2 | Gate `/~{EN2}` mapped to Pico GPIO0; source +3V3; drain +3.3VP | Description incorrectly assigns GPIO15 and implies a separate C2-only supply |
| U2 | Supply +3.3VP | C2 shares the switched peripheral rail |
| R3 | /BABEL_CS to +3.3VP | Flash chip-select pull-up, not SCK |
| R4 | /SD_CS to +3.3VP | SD chip-select pull-up, not MISO |
| R1/R2 | GP26/GP27 to their corresponding expansion nets | Series resistors, not I²C pull-ups |
| J1/J2 | One GPIO signal, +3V3, GND each | Three-pin GPIO expansion, not a complete two-signal I²C port |
| J3 | RX/SCL, TX/SDA, +3V3, GND | Four-pin I²C-capable expansion |
| B1/B2 | /RESET and /BTN_LOCK | Reset and Lock, not page-turn buttons |

These corrections are especially relevant before planning expansion features or using the app to troubleshoot power and buttons.

## Feature exploration: reading library, formats, and display

**User direction (2026-11-15):** treat this as a small-batch, artisan reader. Competitive mass-market pricing is not the target. Consider both customizable units and a streamlined common build after measuring component area, connector access, labor, and the three configuration options. The user plans to host downloadable collections of books, articles, and documents. **Wi-Fi/Bluetooth is deferred for all first-ten configurations** and remains a possible later feature.

**Library software backlog, proposed rather than implemented:** reliable resume at last page; percent read in the master list; favorites; collection-assigned categories and tags without a keyboard; filters and sorting by type and other metadata. The [creator's historical Open Book usage guide](https://www.oddlyspecificobjects.com/projects/openbook/) says its 2022 firmware stored position in `filename.obp`, pagination in `bookname.pag`, and showed up to 15 `.txt` works. It also warns that pagination and metadata parsing were fragile. This establishes an existing design path, **not** current reliability or support for a large hosted catalog. Before committing UI details, inspect a pinned firmware tree and pilot behavior; define stable book identity, total-page/percentage semantics, metadata storage, and behavior when files are renamed or content changes.

**User ruling (2026-11-15), collection organization:** assign categories and tags in collection metadata before download. The reader should consume those labels for its library filters and sorting; it does not need an on-device category editor for the first ten. The Markdown profile and converter must carry the labels into a device-readable manifest or equivalent metadata. Exact vocabulary, multiple-tag rules, display labels, and handling of untagged personal files remain open. Favorites and progress are card-specific state, separate from publisher-assigned categories.

**User ruling (2026-11-15), reader state:** store favorites and reading progress on each microSD card for the first ten. State follows the card when moved to another reader; different cards have independent state. The historical `.obp` position sidecar is a starting point, but its current behavior and file format are unverified. Define how favorites and progress key to a stable book ID, avoid clashes across collections, and specify what happens when a book is updated or removed. Card writes should be checked for interrupted-power behavior before relying on them for saved progress.

| Content option | Reader-side implication | Current assessment |
| --- | --- | --- |
| UTF-8 `.txt` with existing front matter | Closest to the documented firmware; current parser and pagination need validation | Lowest-change pilot format |
| Markdown (`.md`) subset | Could preserve headings, emphasis, and links in editable text, but requires a specified parser, page layout, and treatment of unsupported constructs | Explore on representative books/articles; no firmware support established |
| EPUB 3 | Preserves richer structure, metadata, XHTML/CSS, and packaged assets in a common ebook format | A full on-device reading system is a separate software project; consider off-device conversion to a device format first |

[CommonMark](https://spec.commonmark.org/0.31.2/) defines a baseline Markdown syntax; any custom extensions should be documented so hosted files render predictably. [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/) defines the richer publication container and content model. **Proposed distribution path:** offer source EPUB/Markdown where rights allow, plus a converted device-ready download that the user copies to microSD on Linux. Direct wireless download is a separate feature question. Decide format from sample content and measured pagination, storage, and UI behavior rather than filename preference alone.

**User direction (2026-11-15), format:** compare options first; the user prefers a consistent, customized Markdown format. They expect widely varying file sizes and recognize that some EPUBs contain scanned pages. This is a preferred content direction, not a ruling that the first-ten firmware must parse `.md` directly.

**User ruling (2026-11-15), first-batch content:** prioritize text on the first ten readers. Inline images, diagrams, and scanned/image-only pages can wait. The first device profile should reject or flag unsupported visual content during import rather than silently dropping it. The collection site may retain richer source files and label which downloads have a text-first device edition; exact site behavior remains to be specified.

The Markdown-to-device conversion choice selects the pilot workflow; it does not prove that the existing libros firmware accepts every generated file or that its pagination is reliable. Pin the firmware, define a minimal Markdown profile and converter, then check representative short and long texts on the pilot. Preserve stable source IDs and versions so generated filenames and reading-progress sidecars can be reconciled after updates.

| Path | What it preserves | First-batch work and risk |
| --- | --- | --- |
| Existing `.txt` with control codes | Text, limited metadata, chapters, emphasis | Smallest firmware change; unusual source syntax and fragile historical parser/pagination remain |
| Native custom `.md` on the Pico | Readable headings, emphasis, lists, links, metadata as defined by our profile | Write and validate a streaming parser and layout rules; redesign pagination; specify unsupported constructs |
| Custom `.md` as canonical source, compiled to device-ready text/data | Same editorial source and repeatable output for web and reader | Build a converter and validator; retain source/version mapping for resume and updates; reader format can remain simpler |
| Native EPUB | Original structured text, CSS, images, packaging, metadata | Largest firmware and memory/rendering scope; still does not make image-only pages into reflowable text |
| EPUB import into custom `.md` | Reflowable text and selected semantics after curation | Import quality varies; image-only content needs OCR and review; complex layouts need an explicit fallback |

[W3C's fixed-layout EPUB note](https://www.w3.org/TR/epub-fxl-a11y/) describes image-only publications, so `.epub` alone does not guarantee extractable text. A scan would need OCR plus human correction for a text-first reader; charts, formulas, and illustrations need separate handling. **User ruling (2026-11-15), pilot format:** use a versioned custom Markdown profile as the collection source, with a deterministic Pico-ready text export for the first pilot. Native `.md` support remains an option after measuring parser, layout, and pagination costs on a representative corpus. The profile should define required stable ID/title/type/language, optional author/tags, a bounded subset of headings/emphasis/lists/links, image rejection/flagging, maximum file/page behavior, and an explicit rule for unsupported markup. The site should validate uploads and generate the device file from the same source. Do not set a size cap or promise EPUB import quality before measuring sample books, articles, and documents. Percent read should use the device's actual paginated total and invalidate/rebuild the index if the content or layout changes.

**Display and touch feasibility:** the two checked Good Display storefront listings for plain **GDEY042T81** showed zero stock at review time; this does not prove the panel is unavailable from every supplier. Good Display lists a 400 × 300 [GDEY042T81-T02 touch panel](https://www.good-display.com/product/473.html) using SSD1683 for the display and an FT6336-family I²C touch controller. It has the standard 24-pin display flex **and a separate six-pin touch flex** (GND, VDD, RST, INT, SDA, SCL); its published outline is 91 × 77 × 2.02 mm. A [touch-plus-frontlight model](https://www.good-display.com/product/617.html) adds another six-pin flex and a separate lighting power requirement. The existing C1 J3 exposes an I²C-capable four-pin connection, but the checked C1/C2 route does not provide a direct six-pin touch flex socket or all touch signals there. An adapter/connector, interrupt/reset routing, power and sleep strategy, firmware driver, and mechanical/stock check would be needed. **Inference:** touch is technically viable as an engineering option, but is not a plug-in panel swap for the current build. No touch panel stock, delivered price, or ten-unit compatibility has been qualified. **User ruling:** use the existing buttons for all first-ten boards; retain touch for a later revision.

## Decision register

This register separates the choices for the first ten boards from work that still needs evidence. Record each ruling here before changing the app's canonical data. **Open** means no user decision or validation has been recorded; a proposed baseline above or below is not a ruling.

| Item | Current state | What settles it |
| --- | --- | --- |
| Pico model | Wireless deferred for the first ten; SC0918 in the BOM is Pico W | Use original Pico SC0915 as the reference unless another non-wireless compatibility or supply issue changes the choice; retain Pico W for a future revision |
| C2 assembly route | User prioritizes less hand soldering and rework; complete PCBA is preferred | Check assembled-module availability, compatibility, and a ten-unit quote; keep hand assembly as a fallback |
| Display, C2 values, and firmware | Options requested; GDEY042T81 with PR #11 support is proposed | Compare available panels and driver support; check C2 inductor, pulldown, and current-sense values; reproduce a pinned build and test a pilot |
| Optional expansion | Open; user expects further feature exploration; touch deferred | Map connector/resistor population against proposed first-batch features before freezing the board |
| C1/C2 fabrication revisions | Open; embedded C1 silkscreen says C1-06 while app orders C1-05 | Compare embedded board files to the selected fabrication package; pin file hashes and check interfaces |
| Versions 1–3 | One common PCB design chosen; feature sets and option population open | Define each configuration's populated parts, firmware/content, included parts, and quantity before assigning quotes |
| C2 manufacturing cost | Open; conflicting estimates lack a quote | Obtain a ten-unit quote with setup, components, assembly, shipping, and tax separated |
| C1 BOM completeness | Confirmed missing 1022C retainer | Add the retainer to canonical BOM and purchasing quantities after the build route is chosen |
| Shopping export and build checklist | User wants a complete checklist; current export includes redundant C2 internals | Build a route-aware checklist spanning fabrication, assembly, parts, display, cards, batteries, tools, and spares; keep distributor exports as filtered subsets |
| Circuit and control descriptions | Confirmed conflicts with PCB nets | Correct Q1/Q2, R1–R4, J1–J3, B1/B2 descriptions from the pinned board revision |
| Assembly and font instructions | Confirmed inaccurate | Replace Pico SDK and font-flasher steps with the verified PlatformIO, microSD, and first-boot sequence |
| Price and cost display | Confirmed incomplete and inconsistent | Record dated offers and quantity tiers; show a clearly scoped subtotal and quote-based batch costs |
| Part substitutions | Open | Compare supplier MPNs, footprints, electrical limits, and lifecycle before ordering |
| SD card compatibility | Open | Specify and test one card/filesystem combination on the pilot |
| Reader content format | Custom Markdown source converted to Pico-ready text for pilot; text first | Define the Markdown profile and converter, then validate output and pagination on pinned firmware |
| Tools and pilot acceptance | Basic iron and hand tools available; no multimeter; user will flash, prepare cards, fit displays/batteries, and check units | Clarify computer/USB/SD tools and small-part supplies; add a multimeter, then define inspection, power, display, input, storage, and sleep checks |
| Cases | Deferred by user | Revisit only if the user brings cases back into scope |

**User ruling (2026-11-15):** keep component and manufacturing options open according to availability and possible hardware improvements. Explore the smaller feature ideas after the existing review worklist. The next priority is building instructions that assign manufacturing options to **three versions or configurations, labeled 1, 2, and 3, built on one common PCB design**. Their actual feature sets, optional population, firmware/content, and included parts are still to be defined. No single C2/display/expansion combination is frozen, and no purchase or compatibility conclusion follows from this ruling.

**User ruling (2026-11-15), hardware scope:** compare existing Open Book PCB revisions and compatible parts first for the initial ten boards. A custom PCB revision is outside this first comparison unless the existing routes prove unsuitable or the user changes the scope. The upstream repository contains an ESP32-S3 `OSO-BOOK-B1` design, but the creator [warned in 2023](https://github.com/joeycastillo/The-Open-Book/issues/77) that the then-published version had an EN pull-up error and had not been fully tested. Its present build readiness has not been established. Compare it as an existing revision, without treating it as a proven manufacturing route.

**User ruling (2026-11-15), wireless:** defer Wi-Fi and Bluetooth for all first-ten boards. Keep wireless as a possible future feature. The proposed first-batch content path is download to a Linux computer and transfer by microSD. Do not include Pico W or on-device network features in the reference configuration. Revisit Pico W fit, antenna placement, power, and firmware only when a wireless configuration is proposed.

**User ruling (2026-11-15), input:** use the existing physical buttons for all first-ten boards. Touch is a later feature, not a requirement for configurations 1–3 in this batch. Keep the touch integration findings for a future revision, and do not include a touch panel, touch adapter, or touch firmware in current manufacturing quotes.

**User ruling (2026-11-15), assembly priority:** minimize the user's hand soldering and rework for the first ten. Compare factory assembly of the C1 main board and a complete C2 PCBA before a mainly hand-assembled C1 route. The C1-05 fabrication archive inspected above contains Gerbers and drill files, but no C1 placement file or assembly-ready BOM. Those inputs must be prepared and reconciled to the selected C1 revision before requesting a meaningful C1 PCBA quote. The treatment of through-hole buttons, Pico, battery holder, and other parts must be explicit in each quote; “PCBA” alone does not define how those parts will be installed.

**User ruling (2026-11-15), batch comparison:** quote both sequences for the ten-unit target: one pilot followed by nine, and all ten together. Show separate setup charges, repeated fabrication/assembly fees, component minimums, shipping, tax, lead time, and the cost of any excess boards or parts. This is a request for comparable planning estimates; no vendor quote or order has yet been obtained. Configuration quantities are still open.

**User ruling (2026-11-15), configuration quantities:** decide the allocation among configurations 1–3 **after feature exploration**. The first-ten target remains a planning quantity, not a commitment to ten identical boards or to any particular mix. Quote comparisons can use a clearly labeled reference configuration for now; revisit pricing when the feature sets and quantities are defined.

**User ruling (2026-11-15), common board:** versions 1, 2, and 3 may share the same assembled PCB design and differ in option population, firmware/content, or included parts. Do not create separate board layouts merely to label the three versions. The selected PCB revision and any option-population differences must be explicit in the build checklist and factory quote; a common PCB does not imply identical finished-unit cost.

**User inventory ruling (2026-11-15):** no Open Book hardware or parts are on hand. A pilot requires procurement of its own board, module, display, Pico, and support parts; do not count an existing unit or parts stock against the budget.

**User ruling (2026-11-15), shopping scope:** provide a **complete build checklist for each board configuration**, covering fabrication, assembly, parts, display, microSD cards, batteries, and tools. Include spares, shipping, tax, and any setup charges in the budget view so the checklist represents the cash needed to finish the chosen batch. Show one-time tools separately from per-board parts and distinguish estimated prices from actual quotes. The Digi-Key CSV remains a vendor-specific subset of that complete checklist; when ordering assembled C2 modules it must exclude their internal components.

**User ruling (2026-11-15), final setup:** the user can flash firmware, prepare microSD cards, connect displays, install batteries, and check each unit. Factory quotes should focus on board fabrication, component procurement/population, and solder-joint inspection. Board-level electrical testing can be priced separately, but the user's own acceptance procedure must still cover the display, buttons, storage, USB/battery operation, and sleep/restart behavior. The checklist must include the cables, card reader, cards, batteries, and measurement tools needed for these steps.

**User ruling (2026-11-15), host platform:** use **Linux** for the firmware build, Pico UF2 flashing, and microSD preparation instructions. The exact distro and PlatformIO installation are not yet known. Keep the reproducible firmware revision and display pairing explicit; upstream's prebuilt `book.uf2` is a historical image and not evidence of support for an available replacement panel.

On the current workspace host, neither `pio` nor `platformio` was found on `PATH` during this review. This is a tool-availability observation, not a firmware build result. **User inventory:** a Pico-compatible Micro-USB data cable and a microSD reader are already available; no purchase allowance is needed for those two tools.

## Rulings, 2026-11-17

These supersede the 2026-11-15 rulings about "versions or configurations 1, 2 and 3" above (kept as history). They come from an interview and are rulings, not tested facts.

- **No configurations.** There is one hardware build and one firmware line. Buyers choose which collections are preloaded on their card and can download more from the official site. Formatting guides for authors are to come.
- **Hardware is identical across the first ten.** Existing C1 and C2 revisions, original Pico SC0915, **no J1-J3 expansion fitted** on any unit.
- **Pilot first.** The pilot is the simplest build and runs stock libros with PRs #10 and #11, to prove the board, the C2 and the display. The other nine run the full feature firmware once it exists. Flashing is done by the owner on Linux, so a unit can be reflashed.
- **Box contents:** two AAA cells, a prepared microSD card (fonts and the buyer's chosen collections, tested in the reader), and a quick-start card.
- **Firmware features for the nine:** filter by tag, filter by type, sort by title or author, favorites and recent first, plus resume and percent read from earlier rulings. More ideas welcome. **Spec only:** the spec is `docs/reader-features-spec.md`; someone else writes the code.
- **Quantities:** ten is the planning quantity, one pilot then nine. The earlier "3 / 3 / 3 across configurations" split no longer applies.
- **Still open:** the display and C2 values (see `docs/gdey-c2-values-check.md`), the quotes, the formatting guide for authors, and the site for collections.

## Proposed hardware baseline and fabrication

- C1 main PCB revision to be pinned. C1-05 bare board is a fabrication candidate, two layers and 1.0 mm thick with an appropriate upstream-supported finish such as lead-free HASL or ENIG.
- Original Pico SC0915.
- Complete C2 PCBA module, with its FPC connector installed.
- Monochrome GDEY042T81 panel paired with firmware supporting SSD1683, **conditional on checking C2 component values and a successful pilot**.
- Optional expansion population decided separately; no enclosure in this phase.

The upstream hardware tree observed at commit `6bb483f92e58f4b75d8fcfc72c7c8022f19fe40b` contains:

```text
Fabrication Files/Open Book Main Board/OSO-BOOK-C1-04-rounded.zip
Fabrication Files/Open Book Main Board/OSO-BOOK-C1-05-rounded.zip
Fabrication Files/Castellated E-Paper Driver/OSO-BOOK-C2-02 (PCBWay)/
  OSO-BOOK-C2-02-BOM.csv
  OSO-BOOK-C2-02-PNP.txt
  OSO-BOOK-C2-02_2022-07-19.zip
Fabrication Files/Castellated E-Paper Driver/OSO-BOOK-C2-03 (JLCPCB)/
  OSO-BOOK-C2-03-BOM.csv
  OSO-BOOK-C2-03-PNP.csv
  OSO-BOOK-C2-03.zip
```

Use all files from one matching C2 package. The application embeds C2-02 geometry and BOM, while also recommending C2-03 for JLCPCB. A direct comparison of the pinned [C2-03 BOM](https://raw.githubusercontent.com/joeycastillo/The-Open-Book/6bb483f92e58f4b75d8fcfc72c7c8022f19fe40b/Fabrication%20Files/Castellated%20E-Paper%20Driver/OSO-BOOK-C2-03%20%28JLCPCB%29/OSO-BOOK-C2-03-BOM.csv) with the embedded C2-02 BOM found the same listed 10 µH inductor, 0.47 Ω resistor, capacitor values, connector, MOSFET, and diode roles; R1 changes package from 0603 to 0402. This is a BOM-level comparison, not proof of identical nets, pad geometry, or assembled performance. Neither BOM incorporates a verified GDEY-specific value set.

The embedded `OSO-BOOK-C1.kicad_pcb` contains the back-silkscreen text **`OSO-BOOK-C1-06`**, while `assembly.json` and `AboutView.tsx` direct users to the **C1-05** Gerber zip. The pinned C1-05 [fabrication archive](https://raw.githubusercontent.com/joeycastillo/The-Open-Book/6bb483f92e58f4b75d8fcfc72c7c8022f19fe40b/Fabrication%20Files/Open%20Book%20Main%20Board/OSO-BOOK-C1-05-rounded.zip) has Gerber job revision `05`, 85.1 × 115.1 mm size, two copper layers, and 1.0 mm thickness. Silkscreen text and job metadata establish a revision-label discrepancy, but do not by themselves prove the electrical difference. Compare the copper, holes, board outline, and footprints before ordering or asserting that the visual model is the fabricated board. The downloaded C1-05 ZIP SHA-256 was `a28af22e4787ca4e311a2fb1c486f7d9353da0bae237a103583acbfc15e749bb`.

C2 needs castellated-edge fabrication. Current JLCPCB guidance identifies a special process and extra charge. Quote the actual package, quantity, thickness, finish, assembly service, components, panelization, and delivery destination; do not assume historical service restrictions or estimates still apply.

Sources: [fabrication directory](https://github.com/joeycastillo/The-Open-Book/tree/main/Fabrication%20Files), [upstream hardware README](https://github.com/joeycastillo/The-Open-Book), [JLCPCB castellation guidance](https://jlcpcb.com/help/article/what-is-castellated-holes), [display specification](https://www.good-display.com/product/386.html).

## Quantities for ten units

Quantities below exclude spares and optional expansion:

| Item | Quantity |
| --- | ---: |
| C1 bare main PCB | 10 |
| Fully assembled C2 driver | 10 |
| Original Pico SC0915 | 10 |
| GDEY042T81 monochrome display | 10 |
| GD25Q16CTIGR flash, SOIC/SOP-8 | 10 |
| MEM2075-00-140-01-A microSD socket | 10 |
| Keystone 1022 battery holder | 10 |
| Keystone 1022C retainer | 10 |
| DMG3415U-7 MOSFET | 20 |
| 434351045816 side button | 20 |
| JS102011SAQN power switch | 10 |
| TL1107AF180WQ front button | 70 |
| CL31B106KQHNFNE, 10 µF 1206 capacitor | 20 |
| CL21B105KAFNNNE, 1 µF 0805 capacitor | 10 |
| RMCF1206JT10K0, 10 kΩ 1206 resistor | 20 |
| microSD card | 10 |
| AAA cell | 20 |

Optional expansion for all ten adds 20 S3B-PH-SM4-TB(LF)(SN) connectors, 10 BM04B-SRSS-TB(LF)(SN) connectors, and 20 RC0805JR-071KL resistors. Confirm the desired expansion route before population.

Allow extras for small components and difficult connectors. Ten purchased assemblies do not guarantee ten successful finished units. Choose spare quantities explicitly. The panel carries its flex tail; do not add an unrelated display adapter kit to this baseline.

## Tools and consumables

For hand-assembling C1 with purchased C2 modules:

| Item | Purpose |
| --- | --- |
| Temperature-controlled iron, small chisel and larger tips | Small joints and thermally demanding holder pads |
| Electronics solder, flux, solder wick | Assembly and bridge removal |
| Fine tweezers, PCB holder, magnification, lighting | Placement and inspection |
| Multimeter with continuity and DC voltage | Short and supply checks |
| Tip cleaner, appropriate flux-cleaning supplies, fume extraction | Workstation upkeep and cleaning |
| Micro-USB data cable, computer, microSD reader | Firmware and card preparation |
| Display mounting tape, insulating work surface | Supporting the exposed display during bench work |

Hot air is useful for rework but is not a prerequisite for this route. A current-limited bench supply helps fault diagnosis. No printer is needed while cases are deferred. The complete tool inventory and purchase total are still open.

**User tool inventory (2026-11-15):** basic soldering iron and hand tools; no multimeter. The iron's temperature control, tip sizes, and available flux, solder, wick, tweezers, magnification, and fume extraction remain unspecified. A continuity/DC multimeter is a minimum additional tool for pilot power checks. Price any missing workstation items separately from board materials once the assembly route is chosen.

Plan several sessions for ten units. The app's assembly estimates sum to 195 minutes for its full single-device sequence, including ordering and enclosure steps; this is not a validated labor estimate or a batch schedule. The microSD socket, SOIC flash, and module edges warrant particular attention. A soldered Pico can still be reflashed through USB; removability is not required for normal flashing.

## Manufacturing options to price

These are **assembly routes**, separate from board configurations 1, 2, and 3. Apply each feasible route to both batch sequences (one pilot plus nine, and ten together). Treat supplier capability as unconfirmed until a quote names the actual operations.

| Route | Factory scope to request | Work left to the user |
| --- | --- | --- |
| Full C1 and C2 assembly | Populate C1 SMD and through-hole parts, install Pico, battery holder, and complete C2 module; inspect joints | Firmware, microSD, batteries, display installation, functional checks unless separately quoted |
| Partial C1 plus C2 PCBA | Populate C1 SMD parts and supply complete C2 modules; request a separate price for buttons, holder, Pico, and module installation | Only the operations the factory excludes, plus firmware and functional checks |
| Bare C1 plus C2 PCBA | Fabricate C1 and supply complete C2 modules | Most C1 soldering, firmware, and functional checks; this route is a cost comparison and fallback |

For each route, a useful quote must name the selected C1 revision and C2 package, quantities delivered and billed, component sourcing or consignment, assembly sides, through-hole/manual operations, inspection, setup charges, panelization, shipping to the United States, tax, and lead time. Ask for the **same scope** at quantity one and quantity ten, then price the follow-on nine and any repeated setup charge. Resolve the C1-05/C1-06 discrepancy, display/C2 values, and C1 assembly BOM/placement data before sending a production-ready package. Price the multimeter and any other missing bench tools separately from factory charges.

## Pricing snapshot and limits

USD listings observed during the 2026-11-15 review, before checkout adjustments, shipping, tax, and tariffs. Search excerpts sometimes reflected older promotions; direct product-page text was checked where available.

| Item | Listed price basis | Extension for ten | Source |
| --- | --- | ---: | --- |
| SC0915 | $4.59 each, cut tape | $45.90 | [Digi-Key](https://www.digikey.com/en/products/detail/raspberry-pi/SC0915/13684020) |
| SC0918 Pico W, optional comparison | $7.65 each, cut tape | $76.50 | [Digi-Key](https://www.digikey.com/en/products/detail/raspberry-pi/SC0918/16627943) |
| Keystone 1022 | $4.757 each at 10 | $47.57 | [Digi-Key](https://www.digikey.com/en/products/detail/keystone-electronics/1022/2137859) |
| Keystone 1022C | $0.75 each at 10 | $7.50 | [Digi-Key](https://www.digikey.com/en/products/detail/keystone-electronics/1022C/2746324) |
| GD25Q16CTIGR | $0.825 each at 10 | $8.25 | [Digi-Key](https://www.digikey.com/en/products/detail/gigadevice-electronics-singapore-pte-ltd/GD25Q16CTIGR/9484675) |
| GDEY042T81 | $14.44 promotional display price, but fetched page showed zero stock | Not an available batch quote | [Good Display storefront](https://buy-lcd.com/products/42inch-e-inkanel-spi-interface-buy-eaper-display) |

The flash chip was listed as **Not For New Designs**, with stock shown. Preserve this lifecycle concern; do not replace it with a nominally similar chip without checking package, electrical behavior, and firmware support.

The display search excerpt initially showed $14.96. The later direct page showed **$14.44 and zero stock**. Neither establishes availability of ten panels. Do not reuse the initial promotional figure as a confirmed cart price.

A follow-up availability check found a [second Good Display storefront listing](https://buy-lcd.com/products/42-inch-e-paper-display-morochrome-spi-e-ink-for-digital-price-tags-gdey042t91-578) for GDEY042T81 at **zero stock** as well. Good Display marks [GDEQ042T81 as end of life](https://www.good-display.com/product/443.html) and recommends GDEY042T81. One reseller search result labeled its listing GDEY, but the opened [product page](https://www.laskakit.cz/en/good-display-gdeq042t81-4-2--400x300-epaper-displej/) explicitly identifies **GDEQ042T81**; do not count that stock as ten GDEY panels. An independent reseller listing exists for GDEY, but its quantity and US-delivered terms have not been confirmed. No ten-panel source is qualified yet.

Revised partial subtotal, excluding displays and both bare-PCB/PCBA costs:

```text
Original non-optional C1 electronics excluding display: 10 × ($43.27 − $26.90) = $163.70
Pico price adjustment:                                   10 × ($4.59 − $4.00) =   $5.90
Holder price adjustment:                              10 × ($4.757 − $4.45) =   $3.07
Flash price adjustment:                               10 × ($0.825 − $0.75) =   $0.75
Previously omitted retainers:                                  10 × $0.75 =   $7.50
Provisional subtotal:                                                      $180.92
```

Of that $180.92, **$71.70 still uses old small-component prices**. This is not a fully refreshed BOM or a purchase-ready cart.

Total cash requirement remains:

**$180.92 provisional electronics + ten available displays + C1 fabrication + C2 PCBA + cards/batteries/spares + freight/tax + any tools.**

Obtain a C2 quote with setup fees, component procurement, assembly quantity, and fabrication separated. Count the complete C2 modules once. Distinguish batch cash outlay from per-device allocation and excess parts left over. No reliable all-in total or delivery schedule is established yet.

## Proposed build and validation sequence

1. Freeze revisions, original Pico, exact display model, and expansion population.
2. Create a reproducible PlatformIO build with reviewed fixes. Record source and dependency versions and retain the UF2 plus checksum. A clean compilation does not validate hardware behavior.
3. Confirm ten-panel supply; obtain matching C1 and C2 quotes for US delivery.
4. Kit parts and assemble one pilot unit. Inspect orientation and joints, check for shorts before power, verify supplies, flash firmware, prepare the SD card with fonts and a short text, and check initialization.
5. Verify display refresh, all buttons, SD reading, font loading, USB/battery operation, and sleep/restart behavior on the pilot. Document expected results and actual observations.
6. Assemble the remaining nine using the corrected procedure; keep a per-unit fault/rework record.

No exact voltage-probing procedure, acceptance limits, or firmware image has been validated in this review. Those are next-stage deliverables, not implied guarantees.

## Data foundation before feature work

Priorities are: correct identity and circuit explanations; make purchase lists complete and route-aware; correct firmware/font instructions; and replace undated scalar prices with traceable offers.

For each configuration, the complete checklist should identify the exact board revision, display/C2 pairing, assembly route, required or optional status, quantity per board, ordered quantity including spares, source, quoted or listed unit price, stock observation date, and which party performs installation. Count C2 as one purchased PCBA under an assembled-module route; show its internal BOM as manufacturing detail, not extra purchased items. Give fabrication/setup/freight/tax and one-time tools their own rows. A vendor CSV can export only the rows that vendor can supply, while the full checklist remains the reference for build readiness and batch cash outlay.

Useful future records would include hardware revision and artifact hashes, selected assembly route, exact display/firmware pairing, required versus optional accessories, offer URL/date/currency/quantity breaks/stock, batch fees and shipping, and per-unit build results. These are review recommendations, not approved feature implementation.

## Deferred observations

- The case viewer asserts C1 compatibility for a B1-targeted Sprint 5 design, while the bundled OpenSCAD source defaults to `abridged = false`. Physical fit and exported STL settings were not established. Cases remain out of scope by user instruction.
- The assembly text claims any SD capacity works; this was not verified. Establish a known-working card and filesystem for the pilot instead of carrying that claim forward.
- Some distributor columns list different part numbers or alternatives from the nominal MPN. Full substitution and footprint validation is still open.
- Stock, promotions, PR states, and manufacturing service rules can change. Refresh consequential facts before purchasing.

For continuation instructions and workspace state, see [the handoff](handoff-2026-11-15.md).
