# Reverted Changes — 2026-04-18

Two commits were reverted because the interface was broken. This document
preserves the intent and implementation details so the work can be redone
properly after testing.

---

## Commit 1: `f1a47da` — Fix Digi-Key URLs, add LCSC distributor, price C2 components

### What it did

1. **Digi-Key URL fix**: `/detail/-/-/{pn}` pattern 404s because Digi-Key URLs
   require internal product IDs. Switched to search URLs:
   `https://www.digikey.com/en/products/result?keywords={pn}`

2. **LCSC as third distributor** through the full Rust-to-TypeScript pipeline:
   - `src-tauri/src/types.rs`: added `lcsc_pn: Option<String>` to `BomLine`
   - `src-tauri/src/bom.rs`: added `lcsc_pn` to `ComponentFunction` struct,
     added merge logic in `apply_lookup()`, added `lcsc_pn: None` to both
     C1 and C2 `BomLine` constructors
   - `src/lib/types.ts`: added `lcscPn?: string` to `BomLine`
   - `src/components/BoardView.tsx`: added `lcscPn` prop to `SourceLinks`
   - `src/components/BomView.tsx`: added `lcscPn` prop to `SourceLinks`,
     added `DistributorLink` for LCSC

3. **C2 driver component pricing** in `component_functions.json` — 7 new entries:
   - `0603WAJ047KT5E`: $0.01, LCSC C23703
   - `MGFL2012F100MT-LF`: $0.04, LCSC C281113
   - `CL21B105KBFNNNE`: $0.11, DK 1276-1029-1-ND, Mouser 187-CL21B105KBFNNNE, LCSC C28323
   - `CL21A475KAQNNNE`: $0.11, DK 1276-1244-1-ND, Mouser 187-CL21A475KAQNNNE, LCSC C1779
   - `AFC07-S24ECC-00`: $0.10, LCSC C11092
   - `IRLML0100TRPBF`: $0.55, DK IRLML0100TRPBFCT-ND, Mouser 942-IRLML0100TRPBF, LCSC C53658
   - `LMBR0530T1G`: $0.04, LCSC C18863

4. **Distributor PN merge from JSON**: `apply_lookup()` in `bom.rs` now merges
   `digikey_pn`, `mouser_pn`, `lcsc_pn` from `component_functions.json` when
   the CSV didn't provide them. This lets C2 parts (PCBWay CSV format, no
   distributor columns) get sourcing links via the JSON lookup.

### Key code patterns

```rust
// bom.rs — merge distributor PNs from JSON when CSV didn't provide them
if line.digikey_pn.is_none() {
    line.digikey_pn = cf.digikey_pn.clone();
}
if line.mouser_pn.is_none() {
    line.mouser_pn = cf.mouser_pn.clone();
}
if line.lcsc_pn.is_none() {
    line.lcsc_pn = cf.lcsc_pn.clone();
}
```

```typescript
// Digi-Key search URL (works, unlike the /detail/-/-/ pattern)
`https://www.digikey.com/en/products/result?keywords=${encodeURIComponent(digikeyPn)}`

// LCSC direct product URL
`https://www.lcsc.com/product-detail/${encodeURIComponent(lcscPn)}.html`
```

### Notes
- U2 (OSO-BOOK-C2-01, the castellated module itself) intentionally has no
  price — it's a separate PCBA job costing $30-80 depending on fab house.
- The `SourceLinks` component renders a "Sources" card with Digi-Key, Mouser,
  LCSC, and Datasheet links. It exists in both BoardView and BomView.

---

## Commit 2: `6fc83ca` — Lift 3D viewport into persistent left column

### What it did

Restructured the app so a single `BoardViewport` lives in a persistent left
column (~58% width) in `App.tsx`. Each tab becomes a right-column content
panel that drives the shared viewport through a `ViewportContext`.

### New files

- `src/lib/viewport-context.tsx` — `ViewportConfig` state (sideFilter,
  colorMode, showTraces, highlightedRefs, clickSelectEnabled, focusRefs,
  visible) with a `setConfig(partial)` merge API.

- `src/components/ViewportToolbar.tsx` — Extracted board selector, side
  filter, color-by mode, traces checkbox, component/hole count stats.
  Reads from `useViewport()`, `useNavigation()`, `useDataset()`. Disables
  board selector when `tab === 'assembly'`.

### Changes per file

**`src/App.tsx`**
- Wrapped content in `ViewportProvider`
- Replaced single `<main>` with two-column flex: `ViewportColumn` (left) +
  `<main>` (right)
- `ViewportColumn` renders `ViewportToolbar` + `BoardViewport`, hidden when
  `config.visible === false` or `compact` breakpoint

**`src/components/BoardView.tsx`**
- Stripped to detail panel only (desktop)
- Added tab-activation effect: `clickSelectEnabled: true`, `highlightedRefs: null`
- Added focus-on-select: new selections trigger `focusRefs: [selectedRef]`
- On mobile (compact): renders inline `BoardViewport` + `MobileToolbar`

**`src/components/AssemblyView.tsx`**
- Removed mini viewport from desktop aside
- Added tab-activation: locks board to c1-main, sets `clickSelectEnabled: false`
- Drives `highlightedRefs` and `focusRefs` on step change
- On mobile: renders inline `BoardViewport` with highlights

**`src/components/BomView.tsx`**
- Drives viewport on row selection: sets board, highlightedRefs, focusRefs
- Clicking a C2 part auto-switches viewport to E-Paper Driver board
- Sets `clickSelectEnabled: false` on mount

**`src/components/AboutView.tsx`**
- Sets `visible: false` on mount, viewport column disappears

**`src/lib/navigation-context.tsx`**
- Centralized selection clearing: `setBoard()` now auto-clears `selectedRef`
- `navigateToComponent` uses `setBoardState` directly to avoid the clear

### What worked in testing
- Two-column layout rendered correctly at 1920px
- BOM row selection highlighted components + flew camera to them
- Clicking a C2 row auto-switched the viewport to the driver board
- Assembly step changes drove highlights + camera focus
- `navigateToComponent` from Assembly ref chips to Board tab worked
- About tab hid the viewport column
- Mobile Board and Assembly had inline viewports
- TypeScript, Rust, and web build all clean

### What broke
- The interface was "messed up bad" — exact issues TBD after testing

---

## Preserved files

Copies of key files saved to `/tmp/` for reference:
- `/tmp/component_functions_with_c2.json` — full JSON with C2 pricing
- `/tmp/viewport-context.tsx` — ViewportConfig provider
- `/tmp/ViewportToolbar.tsx` — extracted toolbar component
