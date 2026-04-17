# Accessibility Audit: Making Open Book Builder Readable by a First-Time Builder

> **Status: Implemented** (April 2026). All changes below have been applied
> across commits 4504460–6a5f7b4. A follow-up enrichment pass (cloning the
> upstream repo, cross-referencing schematics and fabrication files) added 3
> new discrepancies, a missing assembly step (babel.bin flash), corrected the
> display part number discrepancy from "naming" to "build-critical", and
> updated the About tab with current project status.

## The problem

The tool currently speaks to someone who already knows what they're looking at.
A person whose inner monologue is "I want to build this e-reader I saw on
GitHub" will land on the app and immediately hit a wall of unexplained
nomenclature: "C1 main", "C2 driver", "BOM", "MPN", "Bbox", "SMD passives",
"castellated edges", "HASL", "Net category". Every tab assumes fluency in PCB
design vocabulary.

This isn't a cosmetic issue. The whole reason the tool exists is to help
someone check their work *before* spending money. If they can't read the tool,
they can't check their work.

## Who is actually using this

The target user is a **motivated maker** — someone comfortable enough with
soldering to attempt a PCB project, but not necessarily an EE. They know what
a soldering iron is. They probably don't know what "castellated" means, what
"HASL" stands for, or why "C1" and "C2" are meaningful identifiers. They've
ordered from Digi-Key before but they navigate by search, not by MPN.

This person doesn't need the tool dumbed down. They need **context bridges**:
enough surrounding information at each decision point that they can either
understand the term or know what to search for. The goal is not to eliminate
technical language — they'll encounter these terms on Digi-Key, in datasheets,
in forum posts. The goal is to never leave them stranded.

## Design principles

1. **UI chrome uses plain English.** Tab labels, toolbar buttons, field labels,
   column headers — these are the parts the user reads hundreds of times. They
   should be immediately legible. Technical designators can appear in
   parentheses or subtitles, not as the primary label.

2. **Data content can be technical.** Assembly step descriptions, discrepancy
   writeups, component function notes — these are reference material the user
   reads once and absorbs. Jargon is acceptable here when it matches what
   they'll see on the parts or in the upstream docs, but first occurrences
   should have parenthetical context.

3. **No separate glossary page.** Nobody reads glossaries. Every term should be
   understandable *in the place it appears*, via inline context, subtitles, or
   a brief parenthetical. If a term needs a glossary entry to make sense,
   the term needs to be replaced or expanded where it's used.

4. **No arbitrary metadata.** Don't add difficulty ratings, skill levels, or
   complexity scores. The assembly descriptions already communicate difficulty
   through their content ("these take flux and a fine tip but don't require
   hot air" tells you more than "Difficulty: 3/5"). Don't add reference
   images — that's a different project.

5. **Explain the two boards once, prominently.** The C1/C2 split is the single
   most confusing thing about this project for a newcomer. It needs a clear,
   unavoidable explanation — not buried in the About tab.

## Specific changes

### Tab labels (App.tsx)

| Current | Proposed | Rationale |
|---------|----------|-----------|
| `Board` | `Board` | Clear enough; the 3D viewport makes it self-evident |
| `BOM` | `Parts List` | "BOM" is industry jargon; "Parts List" is universally understood |
| `Assembly` | `Assembly` | Clear |
| `Discrepancies` | `Discrepancies` | Accurate; "Issues" is too vague, "Warnings" implies a system error |
| `About` | `About` | Clear |

The header status line `"23 BOM rows · 12 discrepancies"` should become
`"23 parts · 12 discrepancies"` — "BOM rows" means nothing to a newcomer.

### Board labels (everywhere they appear)

| Current | Proposed | Rationale |
|---------|----------|-----------|
| `C1 main` | `Main Board` | Descriptive; "C1" is a project-internal designator |
| `C2 driver` | `E-Paper Driver` | Describes what it does, not its project code |

This affects: `BoardView.tsx` (BOARDS array + toolbar pills), `BomView.tsx`
(BOARD_LABEL + filter pills), `App.tsx` header, and any other surface where
these strings appear.

The technical designators `(C1)` and `(C2)` can appear in parentheses in
contexts where the user might need to cross-reference with upstream files, like
the BOM table's board column and the About tab. But they should never be the
primary label.

### Board View detail panel (BoardView.tsx)

| Current label | Proposed label | Note |
|---------------|----------------|------|
| `MPN` | `Part Number` | Universal; MPN can appear in parentheses |
| `Bbox` | `Dimensions` | Nobody outside CAD knows "bbox" |
| `Footprint` | `PCB Footprint` | Marginally clearer; still technical but "PCB" gives context |
| `Pads` | `Solder Points` | Or consider dropping — pad count is not useful to a builder |
| `Net category` | `Signal Type` | "Net" is pure EE jargon; "signal type" communicates the concept |
| `Digi-Key` | `Digi-Key PN` | Already OK but currently inconsistent with the BOM view |

The `Datasheet` field currently shows a raw URL. Better: show "View Datasheet"
as link text, with the URL as the href.

### Board View toolbar (BoardView.tsx)

| Current | Proposed | Rationale |
|---------|----------|-----------|
| `Color: Side \| Net` | `Color by: Board Side \| Signal Type` | "Net" is jargon |
| `Traces` checkbox | `Copper Traces` | Marginally clearer; "traces" alone could mean anything |

The component/hole count `"27 components · 4 mounting holes"` is fine as-is.

### Parts List tab (BomView.tsx)

Table column headers:

| Current | Proposed | Rationale |
|---------|----------|-----------|
| `Refs` | `Ref` | Minor; "Refs" is fine but consider a title attribute explaining what reference designators are |
| `MPN` | `Part Number` | Same as detail panel |
| `Qty` | `Qty` | Universally understood abbreviation |
| `Unit $` / `Line $` | `Unit Cost` / `Line Total` | Slightly clearer |

Footer text `"C2 driver internals excluded from totals — priced as a single
PCBA unit."` should become: `"E-Paper Driver internals excluded — they arrive
pre-assembled as a single unit from the fab house."` "PCBA" is jargon;
"pre-assembled" is plain English and was already used in the assembly steps.

The `"N included · M skipped (no Digi-Key PN)"` helper text should expand "PN"
to "part number".

The detail panel's `"Raw BOM description"` label is fine — it signals "this is
the original data, not my label."

### Assembly tab (AssemblyView.tsx)

**Phase labels** are the biggest problem here. A first-time builder sees
"SMD passives" and has no idea what that means or why it's a phase.

| Current | Proposed | Rationale |
|---------|----------|-----------|
| `SMD passives` | `Surface-mount: resistors & caps` | Says what the parts are |
| `SMD ICs` | `Surface-mount: chips` | "ICs" → "chips" is universally understood |
| `SMD mechanical` | `Surface-mount: connectors` | What they actually are in this build |
| `Through-hole` | `Through-hole parts` | Already the clearest phase name |
| `Modules` | `Pre-built modules` | Clarifies these arrive assembled |
| `Mechanical` | `Mechanical assembly` | Distinguishes from electrical work |
| `Firmware` | `Software setup` | "Firmware" is accurate but "software" is friendlier |

**Assembly intro.** The Assembly tab currently jumps straight into the step
list with no orientation. Add a brief intro block above the progress header —
not a wall of text, just 2-3 sentences:

> You're building the Open Book from bare boards to working e-reader. Most of
> the work happens on the **Main Board** — the E-Paper Driver module arrives
> pre-assembled from the fab house and gets soldered on in one step.

This could also surface the total tool list (aggregated from all steps) so the
builder can gather everything before starting. Not a separate "Before you
begin" card — just a collapsible "Tools you'll need" line under the intro.

**Assembly step descriptions** (assembly.json) are already well-written. A few
specific parenthetical additions would help:

- `"castellated edges"` → `"castellated edges (the row of half-circle pads
  along the board edge)"`
- `"HASL"` → `"HASL (the metallic coating on the copper pads)"`
- `"PCBA"` → `"pre-assembled module"` (replace the acronym entirely)
- `"SOIC-8"` → `"SOIC-8 (8-pin chip package)"` — only on first occurrence
- `"SOT-23"` → `"SOT-23 (3-pin chip package)"` — only on first occurrence
- `"drag-solder technique"` → `"drag-solder technique (run the iron tip
  slowly across all pins at once)"`
- `"FFC"` → `"FFC (flat ribbon cable)"`
- `"BOOTSEL"` → `"BOOTSEL (the small button on the Pico board)"`
- `"FAT"` → `"FAT (the standard SD card format — most cards ship this way)"`

These are small edits to assembly.json, not structural changes.

### Discrepancy tab (DiscrepancyView.tsx)

The discrepancy descriptions are dense but accurate. Two specific jargon
issues:

- `"HASL"` in the PCBWay finish discrepancy — expand on first use: `"HASL
  (Hot Air Solder Leveling — the metallic surface finish on the board)"`
- `"ENIG"` — expand: `"ENIG (a gold-plated finish alternative)"`
- `"RoHS-noncompliant"` — expand: `"RoHS-noncompliant (contains restricted
  hazardous substances under EU law)"`
- `"PCBA"` everywhere → `"pre-assembled board"` or expand

The severity labels (Build-critical, Cost impact, Naming, Informational) are
already clear.

### About tab (AboutView.tsx)

The About tab is supposed to orient newcomers, but it currently uses jargon
in the very section meant to explain things:

- `"castellated submodule"` → `"a small daughter board that solders onto the
  main board via half-circle edge pads (called 'castellations')"`
- `"level-shifts the SPI bus"` → `"converts signal voltages between the Pico
  and the display"` (a builder doesn't need to know what SPI is here)
- `"2-layer"` → `"a simple two-layer board"` or drop the layer count entirely
  (irrelevant to a builder)
- `"upstream repo"` → `"the original project repository"` or just `"the
  project's GitHub"` — "upstream" is Git jargon
- `"KiCad and EAGLE source files"` → `"the original circuit board design
  files (KiCad for the main board, EAGLE for the driver module)"`
- `"Tauri v2 + React 19 + Three.js"` — this whole sentence is for developers,
  not builders. Consider moving it to a "For developers" subsection or
  dropping it from the main flow.

### Header status line (App.tsx)

`"23 BOM rows · 12 discrepancies"` → `"23 parts · 12 discrepancies"`

Or better: `"23 parts across 2 boards · 12 discrepancies (2 build-critical)"`
— this gives the newcomer an immediate sense of what the numbers mean and
whether they should be alarmed.

### Discrepancy banner (DiscrepancyBanner.tsx)

Current: `"N unresolved build-critical issue(s) — review before ordering from
PCBWay or Digi-Key."`

This is actually good — it names the vendors the user is about to give money
to, which creates urgency. Keep it, but consider expanding: `"review before
ordering boards from PCBWay or parts from Digi-Key"` — the word "boards" and
"parts" clarify what each vendor sells.

## What NOT to change

- **Component reference designators** (C1, R3, U2, etc.) These are printed on
  the physical board. The user will see them through a magnifying glass while
  soldering. Renaming them in the app would create a disconnect.

- **Part numbers** (DMG3415U-7, GD25Q16C, etc.) These are what the user types
  into Digi-Key. Simplifying them hides the ordering information.

- **Electrical units** (µF, kΩ, V). Standard units the user will see on every
  datasheet and parts listing. If they're building electronics, they'll learn
  these quickly.

- **Package sizes** (0805, 1206, SOT-23). These appear on the Digi-Key
  listing and the physical components. But do add a parenthetical on first
  occurrence in assembly descriptions: `"0805 (2mm × 1.25mm)"`.

- **Vendor names** (PCBWay, JLCPCB, Digi-Key). Proper nouns; the user will
  navigate to these sites. The About tab or assembly step 1 can briefly note
  what each one is ("PCBWay and JLCPCB are PCB fabrication services; Digi-Key
  is an electronic parts distributor").

- **The assembly step content quality.** The descriptions are genuinely good —
  they tell the builder what to do, in what order, with what tools, and what
  to watch out for. They just need a few parenthetical bridges for first-time
  readers.

## Implementation approach

This is mostly string changes — the vast majority of the work is editing
labels, adding parentheticals, and adjusting a few data descriptions. No
architectural changes. No new components (except possibly a 2-3 line intro
block on the Assembly tab).

Rough grouping:

1. **UI chrome labels** (~30 minutes) — tab name, board labels, detail panel
   field labels, toolbar text, column headers. All in .tsx files.

2. **Assembly data enrichment** (~30 minutes) — parenthetical expansions in
   assembly.json for jargon terms on first occurrence. Phase labels in
   AssemblyView.tsx.

3. **Discrepancy data enrichment** (~15 minutes) — expand HASL/ENIG/RoHS/PCBA
   on first occurrence in discrepancies.json.

4. **About tab rewrite** (~20 minutes) — de-jargon the orientation copy;
   move developer-facing tech stack details to a subsection.

5. **Assembly intro block** (~20 minutes) — brief orientation above the step
   list explaining the two-board structure and surfacing the aggregated tool
   list.

Each group is independently committable and independently valuable.

## Measure of success

A person reading the Assembly tab for the first time can understand every
step well enough to execute it without needing to Google a term that appears
in the UI. Technical terms in the *data* (part numbers, electrical specs) are
acceptable — those are inherent to the domain. But the *app's own voice*
(labels, headers, descriptions, phase names) should never be the source of
confusion.
