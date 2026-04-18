# Viewport Redesign — Proposed Directions

> **Status:** Proposal. None of these directions are implemented yet.
> Direction C is recommended.

The app currently has four independent tabs. The 3D viewport lives in
two places: a full-size instance on the Board tab, and a 380x320 px
mini instance on the Assembly tab. Switching tabs destroys and recreates
WebGL contexts. The Parts List tab has no 3D integration at all.

This document describes three directions for unifying the viewport
experience so it becomes the persistent visual anchor of the app.

---

## Direction A: Single-Page Dashboard

Collapse all four tabs into one scrollable page. The 3D viewport sits
in a fixed top section (~50% of the viewport height), and all content
flows below it in collapsible sections: Parts List, Assembly Steps,
and About/Ordering info.

**Layout:**
```
+--------------------------------------------------+
| Header                                           |
+--------------------------------------------------+
| 3D Viewport (50vh, sticky)                       |
| [Board toggle] [Side filter] [Color] [Traces]   |
+--------------------------------------------------+
| v Parts List (collapsible)                       |
|   BOM table, export button, cost footer          |
+--------------------------------------------------+
| v Assembly (collapsible)                         |
|   Step checklist, progress, tools                |
+--------------------------------------------------+
| v Ordering & About (collapsible)                 |
|   PCB specs, display info, credits               |
+--------------------------------------------------+
```

**Viewport interaction:** Clicking a BOM row or assembly step
highlights the relevant components in the viewport above. Scrolling
to a section could auto-configure the viewport (e.g. scrolling to
Assembly locks the board to Main Board).

**Pros:**
- Everything on one page — no tab switching, no lost context.
- The viewport is always visible while reading any section.
- Simplest mental model: scroll down = more detail.

**Cons:**
- Vertical space is scarce — the viewport competes with content.
- Sections that need lots of vertical space (BOM table with 23 rows,
  13 assembly steps) fight for scroll real estate.
- Mobile: sticky viewport on small screens is painful.
- The About/ordering content doesn't benefit from the viewport at all
  but still shares the page.
- Significant departure from the current tab-based navigation pattern.

---

## Direction B: Sub-tabs / Modes Within a Unified Shell

Keep the tab structure but add sub-tabs or modes within each tab that
cross-link to the others. The viewport stays per-tab (Board and
Assembly each have their own instance) but gains shared state so
switching between Board and Assembly preserves camera position and
filter settings.

**Layout:**
```
+--------------------------------------------------+
| Header  [Board] [Parts List] [Assembly] [About]  |
+--------------------------------------------------+
| (Board tab)                                      |
| [Viewport + toolbar]          | Detail panel     |
|                               | + BOM quick-view |
|                               | + Assembly refs  |
+--------------------------------------------------+
```

Each tab's detail panel gains cross-links: the Board detail panel
shows which assembly step uses the selected component; the Parts List
detail panel shows a mini component locator; the Assembly step panel
links to the Board tab with that step's refs pre-selected.

**Viewport interaction:** Shared camera state (position, target,
filter settings) persisted in context so switching between Board and
Assembly tabs doesn't reset the view.

**Pros:**
- Least disruptive — tabs stay, each gains cross-references.
- Detail panels become richer without layout changes.
- Each tab keeps its own scroll position and local state.

**Cons:**
- Still destroys/recreates WebGL on tab switch (even with shared
  camera state, there's a flash).
- Parts List still has no viewport — the cross-link is just a
  "jump to Board" button, not a live highlight.
- Adds complexity to each tab without fundamentally solving the
  "one viewport, many uses" problem.
- Risk of clutter: too many cross-links in every detail panel.

---

## Direction C: Persistent Viewport Column (Recommended)

Lift the viewport into a persistent left column (~58% width). Tab
content renders in the right column (~42%). Each tab drives the shared
viewport differently through a `ViewportContext`. The viewport is never
destroyed — switching tabs just changes what drives it.

**Layout:**
```
+--------------------------------------------------+
| Header  [Board] [Parts List] [Assembly] [About]  |
+--------------------------------------------------+
| Viewport Toolbar                   |             |
| [Board] [Side] [Color] [Traces]   |             |
|                                    |  Tab        |
| +--------------------------------+ |  Content    |
| |                                | |  (right     |
| |   3D Viewport (persistent)     | |   column)   |
| |                                | |             |
| |                                | |             |
| +--------------------------------+ |             |
+--------------------------------------------------+
```

**How each tab drives the viewport:**

| Tab | Click-select | Highlights | Camera | Board lock |
|-----|-------------|------------|--------|------------|
| Board | Enabled | None | Flies to selected component | User choice |
| Parts List | Disabled | BOM row refs | Flies to highlighted refs | Auto-switches to match row |
| Assembly | Disabled | Step component refs | Flies to highlighted refs | Locked to Main Board |
| About | N/A | N/A | N/A | N/A (viewport hidden) |

**Camera animation:** A `focusOnRefs()` method on the scene renderer
computes the bounding box of target components, calculates a camera
position that frames them (preserving the current viewing angle), and
tweens the camera over ~0.4s with easeInOutCubic easing. User
interaction (clicking/dragging the viewport) cancels the tween
immediately.

**Key architectural changes:**

1. **`ViewportContext`** — shared config state:
   - `sideFilter`, `colorMode`, `showTraces` (toolbar-controlled,
     persist across tab switches)
   - `highlightedRefs`, `focusRefs` (per-tab, set by activation
     effects)
   - `clickSelectEnabled` (false on Assembly/Parts List)
   - `visible` (false on About)

2. **`ViewportToolbar`** — extracted from BoardView, always visible
   alongside the persistent viewport. Board selector disabled on
   Assembly tab (locked to Main Board).

3. **`focusOnRefs()`** in scene-renderer — tween system in the
   animation loop, cancelled on pointerdown.

4. **`NavigationContext.setBoard()`** — would auto-clear `selectedRef`
   so consumers don't need to remember to do it manually.

5. **App.tsx two-column layout** — `ViewportProvider` wraps a flex
   container with persistent viewport left + tab content right.
   About tab hides the viewport column and content fills full width.

**Pros:**
- One WebGL context for the entire session — no destroy/recreate flash.
- Every tab gets live 3D integration for free.
- Parts List gets the biggest upgrade: clicking a row highlights and
  flies to those components. Clicking a C2 part auto-switches the
  viewport to the E-Paper Driver board.
- Assembly steps orbit the camera to frame the relevant components
  instead of relying on a tiny 320px mini viewport.
- Toolbar state persists across tabs — set your preferred color mode
  once and it stays.
- About tab still gets full-width layout by hiding the viewport.

**Cons:**
- Right column is narrower (~42%) — BOM table columns are tighter.
- The 3D viewport is always consuming GPU resources even when the user
  is reading text-heavy content on the Parts List or Assembly tabs.
- More complex state management (ViewportContext + NavigationContext
  coordination).
- Requires careful effect ordering: each tab's activation effect must
  set the right config without racing against the previous tab's
  cleanup.

**Files touched:**

| File | Change |
|------|--------|
| `src/lib/scene-renderer.ts` | Add `focusOnRefs`, tween system |
| `src/lib/viewport-context.tsx` | **New** — config state + provider |
| `src/lib/navigation-context.tsx` | Auto-clear selection in setBoard |
| `src/components/BoardViewport.tsx` | Add `focusRefs` prop |
| `src/components/ViewportToolbar.tsx` | **New** — extracted toolbar |
| `src/App.tsx` | Two-column layout + ViewportProvider |
| `src/components/BoardView.tsx` | Strip to detail panel only |
| `src/components/AssemblyView.tsx` | Remove mini viewport, drive shared |
| `src/components/BomView.tsx` | Wire row selection to viewport |
| `src/components/AboutView.tsx` | Hide viewport on mount |
