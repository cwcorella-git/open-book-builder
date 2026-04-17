// Three.js scene for the Board tab. `initScene()` builds a renderer + scene
// from a `BoardData` and returns a `SceneState` the React wrapper can drive
// imperatively (side filter, selection highlight) without re-initializing
// the WebGL context. The dispose idiom tracks every BufferGeometry/Material
// we create for teardown.
//
// Coordinate conventions (also documented in the task #9 plan section):
// - Board sits in the X–Z plane; +Y is up (out of the top copper face).
// - Board thickness is BOARD_THICKNESS mm; top face at y = BOARD_THICKNESS.
// - KiCad origin is top-left with Y growing down. We map:
//     three_x = x_kicad - widthMm/2
//     three_z = y_kicad - heightMm/2
//   so the board is centered on the origin and a smaller KiCad Y (top edge
//   of the board as drawn in KiCad) lands at a more-negative Z, which is
//   screen-up with `camera.up = (0, 0, -1)` and the overhead camera.
// - Component rotation: KiCad's positive rotation is CCW viewed from above
//   the top face (+Y here). CCW around +Y in Three.js takes +X → -Z, which
//   matches KiCad's +X → +Y_kicad = +Z_three, so we negate:
//     mesh.rotation.y = -degToRad(c.rotation)
// - The board outline's THREE.Shape is built in its own XY plane with Y
//   flipped (`shape_y = heightMm/2 - y_kicad`) so that after rotating the
//   extrude geometry by -π/2 around X the shape-Y axis lines up with -Z and
//   everything ends up oriented the same as the direct-placement components.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { buildHeroMesh } from './hero-meshes';
import type {
  BoardData,
  Component,
  CopperLayer,
  CopperSegment,
  EdgeSegment,
  Hole,
  NetCategory,
  Side,
  SilkscreenLayer,
  Via,
} from './types';

export type SideFilter = 'both' | 'top' | 'bottom';
export type ColorMode = 'side' | 'netCategory';

export interface SceneState {
  dispose(): void;
  setSideFilter(filter: SideFilter): void;
  setSelectedRef(ref: string | null): void;
  /**
   * Drive the Assembly-view multi-highlight. Passing a non-empty ref list
   * dims every other component to `DIM_OPACITY` and emissive-tints the
   * listed refs at `HIGHLIGHT_INTENSITY_MULTI`. `null` or `[]` reverts
   * everything. See also `applySelection` — the two paths share the
   * primaryMaterial.emissive channel, but in practice each SceneState only
   * drives one (Board tab → click selection; Assembly tab → step refs).
   */
  setHighlightedRefs(refs: ReadonlyArray<string> | null): void;
  setColorMode(mode: ColorMode): void;
  setTracesVisible(visible: boolean): void;
  /** Smoothly orbit the camera to frame the given component refs. */
  focusOnRefs(refs: ReadonlyArray<string>): void;
  onSelect: ((ref: string | null) => void) | null;
}

// Net-category → hex color palette for the netCategory color mode.
const CATEGORY_COLORS: Record<NetCategory, number> = {
  power:   0xef4444, // red
  ground:  0x64748b, // slate
  spi:     0xf59e0b, // amber
  i2c:     0x22d3ee, // cyan
  gpio:    0xa3e635, // lime
  debug:   0xc084fc, // violet
  analog:  0xfb923c, // orange
  other:   0x475569, // dim slate
};

const BOARD_THICKNESS_MM = 1.0;
const BOARD_COLOR = 0x1e293b;
const TOP_COLOR = 0xf59e0b;
const BOTTOM_COLOR = 0x38bdf8;
const HIGHLIGHT_EMISSIVE = 0xf8fafc;
// Dimmer than the click-selection 0.5 so when an Assembly step is being
// viewed, the multi-highlight reads as "grouped" rather than "picked".
const HIGHLIGHT_INTENSITY_MULTI = 0.35;
const HIGHLIGHT_INTENSITY_SELECTION = 0.5;
const DIM_OPACITY = 0.25;
const BACKGROUND_COLOR = 0x0b1220;

const ARC_SEGMENTS = 16;
const CLICK_DRAG_THRESHOLD_PX = 4;

// Silkscreen overlay constants. 8 px/mm yields ~680×920 px for C1 (~2.4 MB
// VRAM uncompressed per face) and ~138×191 px for C2 — fine for both targets.
// 0.12 mm stroke matches typical fab white-silk line-width.
const SILK_PX_PER_MM = 8;
const SILK_COLOR = '#e2e8f0';
const SILK_LINE_MM = 0.12;
const SILK_Y_OFFSET_MM = 0.01;

// Copper trace overlay constants. Traces sit just above the silk overlays
// so they're visible but behind component meshes in the depth buffer.
const TRACE_TOP_COLOR = 0xf59e0b; // amber — matches top-side component tint
const TRACE_BOTTOM_COLOR = 0x38bdf8; // cyan — matches bottom-side tint
const TRACE_Y_OFFSET_MM = 0.015;
const VIA_COLOR = 0xd4af37; // gold
const VIA_SEGMENTS = 8; // cylinder tessellation

export function initScene(
  container: HTMLElement,
  boardData: BoardData,
  initialSideFilter: SideFilter,
  initialSelectedRef: string | null,
  initialHighlightedRefs: ReadonlyArray<string> | null = null,
): SceneState {
  // Defensive pre-clear: React StrictMode double-mounts us in dev, and any
  // prior init that threw may have left an orphaned canvas behind.
  while (container.firstChild) container.removeChild(container.firstChild);

  const { widthMm, heightMm, edgeSegments, holes } = boardData.outline;

  // --- Renderer + camera + controls ----------------------------------------

  const cw = Math.max(container.clientWidth, 1);
  const ch = Math.max(container.clientHeight, 1);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BACKGROUND_COLOR);

  const camera = new THREE.PerspectiveCamera(45, cw / ch, 0.1, 1000);
  camera.position.set(0, 150, 0);
  camera.up.set(0, 0, -1);
  camera.lookAt(0, 0, 0);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  // `false` keeps the flex-sized canvas style intact — Three.js otherwise
  // overwrites width/height styles on the DOM element.
  renderer.setSize(cw, ch, false);
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.minDistance = 20;
  controls.maxDistance = 400;
  controls.target.set(0, 0, 0);

  // --- Lighting ------------------------------------------------------------

  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const directional = new THREE.DirectionalLight(0xffffff, 0.8);
  directional.position.set(50, 200, 50);
  scene.add(directional);

  // --- Ownership tracking --------------------------------------------------
  //
  // Shared palette + lights are page-lifetime; anything we `new` per board
  // (geometries, cloned materials) must dispose with the state.

  const ownedGeometries = new Set<THREE.BufferGeometry>();
  const ownedMaterials = new Set<THREE.Material>();
  // CanvasTextures carry GPU texture handles; hero-mesh labels are the only
  // source today but the set is always initialized so dispose() stays simple.
  const ownedTextures = new Set<THREE.Texture>();

  // --- Board mesh ----------------------------------------------------------

  const boardShape = buildBoardShape(edgeSegments, holes, widthMm, heightMm);
  if (boardShape) {
    const boardGeom = new THREE.ExtrudeGeometry(boardShape, {
      depth: BOARD_THICKNESS_MM,
      bevelEnabled: false,
    });
    // Rotate so the extrude axis (+Z in shape space) points +Y in world,
    // and shape-Y lines up with -Z so KiCad top-of-board sits at screen-up.
    boardGeom.rotateX(-Math.PI / 2);
    const boardMat = new THREE.MeshStandardMaterial({
      color: BOARD_COLOR,
      flatShading: true,
    });
    const boardMesh = new THREE.Mesh(boardGeom, boardMat);
    scene.add(boardMesh);
    ownedGeometries.add(boardGeom);
    ownedMaterials.add(boardMat);
  }

  // --- Silkscreen overlays -------------------------------------------------
  //
  // Task #13a: two thin PlaneGeometry overlays floated 0.01 mm above each
  // face, textured with rasterized vector silk. `depthWrite: false` keeps
  // hero-mesh castellations visible where silk would otherwise occlude them.
  // Empty layers skip — no wasted GPU texture handle.

  for (const face of ['top', 'bottom'] as const) {
    const layer =
      face === 'top'
        ? boardData.outline.silkscreenTop
        : boardData.outline.silkscreenBottom;
    const overlay = buildSilkscreenOverlay(
      layer,
      widthMm,
      heightMm,
      face,
      BOARD_THICKNESS_MM,
    );
    if (!overlay) continue;
    scene.add(overlay.mesh);
    ownedGeometries.add(overlay.geometry);
    ownedMaterials.add(overlay.material);
    ownedTextures.add(overlay.texture);
  }

  // --- Copper trace overlays -------------------------------------------------
  //
  // Task #13f: LineSegments per copper layer + CylinderGeometry per via.
  // Default hidden; toggled by the "Show traces" checkbox in BoardView.

  const traceGroup = new THREE.Group();
  traceGroup.visible = false;
  scene.add(traceGroup);

  for (const face of ['f-cu', 'b-cu'] as const) {
    const layerTraces = boardData.traces.filter((t) => t.layer === face);
    if (layerTraces.length === 0) continue;
    const result = buildTraceLines(
      layerTraces,
      widthMm,
      heightMm,
      face,
      BOARD_THICKNESS_MM,
    );
    traceGroup.add(result.mesh);
    ownedGeometries.add(result.geometry);
    ownedMaterials.add(result.material);
  }

  if (boardData.vias.length > 0) {
    const result = buildVias(
      boardData.vias,
      widthMm,
      heightMm,
      BOARD_THICKNESS_MM,
    );
    traceGroup.add(result.mesh);
    ownedGeometries.add(result.geometry);
    ownedMaterials.add(result.material);
  }

  const applyTracesVisible = (visible: boolean) => {
    traceGroup.visible = visible;
  };

  // --- Component meshes ----------------------------------------------------
  //
  // Two paths: components with `heroMeshId` go through `buildHeroMesh` to get
  // a procedural Group (Pi Pico / C2 module / battery holder / microSD).
  // Everything else gets the extruded-bbox Box.
  //
  // Both paths return an entry tracking:
  //   - `root`: the Object3D added to the scene (Group or Mesh); side filter
  //     toggles its `.visible`.
  //   - `primaryMaterial`: the MeshStandardMaterial that receives the
  //     emissive selection tint. For boxes that's the mesh's own material;
  //     for hero meshes it's the body material from the builder.
  //
  // The root carries `userData.ref` so the raycaster can identify hits via
  // a `.parent`-walk (recursive intersection on Groups returns deep children).
  interface ComponentEntry {
    ref: string;
    side: Side;
    dominantCategory: NetCategory | undefined;
    root: THREE.Object3D;
    primaryMaterial: THREE.MeshStandardMaterial;
    // The side-based color (orange top / cyan bottom) assigned at construction
    // time. Stored so `setColorMode('side')` can revert to it.
    sideColor: number;
    // Every MeshStandardMaterial on this component's mesh tree. For boxes
    // that's just [primaryMaterial]; for hero meshes it's body + castellations
    // + USB + any other extruded parts. MeshBasicMaterial labels are excluded
    // on purpose — they ride alpha textures that dimming via opacity mangles.
    allMaterials: THREE.MeshStandardMaterial[];
  }
  const componentEntries: ComponentEntry[] = [];

  for (const c of boardData.components) {
    const entry = c.heroMeshId
      ? buildHeroEntry(c, widthMm, heightMm)
      : buildBoxEntry(c, widthMm, heightMm);
    if (!entry) continue;
    scene.add(entry.root);
    const standardMats = entry.materials.filter(
      (m): m is THREE.MeshStandardMaterial => m instanceof THREE.MeshStandardMaterial,
    );
    componentEntries.push({
      ref: c.ref,
      side: c.side,
      dominantCategory: c.dominantCategory ?? undefined,
      root: entry.root,
      primaryMaterial: entry.primaryMaterial,
      sideColor: c.side === 'top' ? TOP_COLOR : BOTTOM_COLOR,
      allMaterials: standardMats,
    });
    for (const g of entry.geometries) ownedGeometries.add(g);
    for (const m of entry.materials) ownedMaterials.add(m);
    for (const t of entry.textures) ownedTextures.add(t);
  }

  // --- Selection + side filter ---------------------------------------------

  let currentlySelected: ComponentEntry | null = null;

  // Multi-highlight state (Assembly view). `highlightedRefKey` is a stable
  // sorted "|"-joined string so repeated calls with equivalent arrays
  // short-circuit. `originalOpacities` lazily captures each material's
  // authored opacity on first dim so revert restores the real value rather
  // than hard-coding 1.0.
  let highlightedRefKey: string | null = null;
  const originalOpacities = new WeakMap<THREE.MeshStandardMaterial, number>();

  const applySideFilter = (filter: SideFilter) => {
    for (const e of componentEntries) {
      e.root.visible = filter === 'both' ? true : e.side === filter;
    }
  };

  const applySelection = (ref: string | null) => {
    if (currentlySelected) {
      currentlySelected.primaryMaterial.emissive.setHex(0x000000);
      currentlySelected = null;
    }
    if (ref) {
      const entry = componentEntries.find((e) => e.ref === ref);
      if (entry) {
        entry.primaryMaterial.emissive.setHex(HIGHLIGHT_EMISSIVE);
        entry.primaryMaterial.emissiveIntensity = HIGHLIGHT_INTENSITY_SELECTION;
        currentlySelected = entry;
      }
    }
  };

  const applyHighlightedRefs = (refs: ReadonlyArray<string> | null) => {
    // Normalize: null/empty → "clear"; otherwise dedupe + sort to a stable
    // key so callers that pass a new array identity each render don't re-run
    // the GPU work.
    const cleared = refs == null || refs.length === 0;
    const key = cleared ? null : [...new Set(refs)].sort().join('|');
    if (key === highlightedRefKey) return;
    highlightedRefKey = key;

    if (cleared) {
      // Revert every captured material to its authored opacity + clear
      // emissive (except whatever `applySelection` is currently holding).
      for (const entry of componentEntries) {
        for (const m of entry.allMaterials) {
          const original = originalOpacities.get(m);
          if (original !== undefined) {
            m.opacity = original;
            m.transparent = original < 1;
          }
        }
        if (entry !== currentlySelected) {
          entry.primaryMaterial.emissive.setHex(0x000000);
        }
      }
      return;
    }

    const refSet = new Set(refs);
    for (const entry of componentEntries) {
      // Capture original opacity once per material.
      for (const m of entry.allMaterials) {
        if (!originalOpacities.has(m)) originalOpacities.set(m, m.opacity);
      }

      if (refSet.has(entry.ref)) {
        // In-group: restore full opacity + emissive tint at multi-intensity.
        for (const m of entry.allMaterials) {
          const original = originalOpacities.get(m) ?? 1;
          m.opacity = original;
          m.transparent = original < 1;
        }
        // Selection (intensity 0.5) wins over multi-highlight (0.35) when
        // both apply to the same ref — don't step on it.
        if (entry !== currentlySelected) {
          entry.primaryMaterial.emissive.setHex(HIGHLIGHT_EMISSIVE);
          entry.primaryMaterial.emissiveIntensity = HIGHLIGHT_INTENSITY_MULTI;
        }
      } else {
        // Out-of-group: dim to DIM_OPACITY. Clear emissive except on the
        // currently selected entry.
        for (const m of entry.allMaterials) {
          m.opacity = DIM_OPACITY;
          m.transparent = true;
        }
        if (entry !== currentlySelected) {
          entry.primaryMaterial.emissive.setHex(0x000000);
        }
      }
    }
  };

  const applyColorMode = (mode: ColorMode) => {
    for (const entry of componentEntries) {
      const color =
        mode === 'netCategory'
          ? CATEGORY_COLORS[entry.dominantCategory ?? 'other']
          : entry.sideColor;
      entry.primaryMaterial.color.setHex(color);
    }
  };

  applySideFilter(initialSideFilter);
  applySelection(initialSelectedRef);
  applyHighlightedRefs(initialHighlightedRefs);

  // --- Click-to-select -----------------------------------------------------
  //
  // OrbitControls consumes drag events but still lets `click` fire at the
  // end of a rotation. Track pointerdown/up and only treat as a pick if the
  // pointer barely moved — otherwise camera rotation would keep clearing
  // the selection.

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let pointerDownAt: { x: number; y: number } | null = null;

  const onPointerDown = (e: PointerEvent) => {
    pointerDownAt = { x: e.clientX, y: e.clientY };
    tweenActive = false; // cancel camera animation on user interaction
  };

  const onPointerUp = (e: PointerEvent) => {
    const down = pointerDownAt;
    pointerDownAt = null;
    if (!down) return;
    if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > CLICK_DRAG_THRESHOLD_PX) {
      return;
    }
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    // Recursive=true so hero-mesh child meshes (castellations, USB housing,
    // label planes) all count as hits. Walk up to the root whose userData.ref
    // was set by buildBoxEntry / buildHeroEntry.
    const roots = componentEntries.map((e) => e.root);
    const hits = raycaster.intersectObjects(roots, true);
    const ref = hits.length > 0 ? findRootRef(hits[0].object) : null;
    state.onSelect?.(ref);
  };

  renderer.domElement.addEventListener('pointerdown', onPointerDown);
  renderer.domElement.addEventListener('pointerup', onPointerUp);

  // --- Resize --------------------------------------------------------------
  //
  // ResizeObserver on the container, not window. The detail panel reflows
  // when selection changes, which triggers a flex resize that `resize` on
  // `window` would miss.

  const resizeObserver = new ResizeObserver(() => {
    const w = Math.max(container.clientWidth, 1);
    const h = Math.max(container.clientHeight, 1);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  });
  resizeObserver.observe(container);

  // --- Camera tween (focusOnRefs) ------------------------------------------

  const TWEEN_SPEED = 2.5; // completes in ~0.4s
  let tweenActive = false;
  const tweenStartPos = new THREE.Vector3();
  const tweenEndPos = new THREE.Vector3();
  const tweenStartTarget = new THREE.Vector3();
  const tweenEndTarget = new THREE.Vector3();
  let tweenProgress = 0;

  function easeInOutCubic(t: number): number {
    return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
  }

  function focusOnRefs(refs: ReadonlyArray<string>): void {
    if (refs.length === 0) return;

    const box = new THREE.Box3();
    let found = false;
    let topCount = 0;
    let bottomCount = 0;
    for (const entry of componentEntries) {
      if (refs.includes(entry.ref)) {
        box.expandByObject(entry.root);
        found = true;
        if (entry.side === 'top') topCount++;
        else bottomCount++;
      }
    }
    if (!found) return;

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z, 1);

    const fovRad = THREE.MathUtils.degToRad(camera.fov / 2);
    const dist = Math.min(
      Math.max((maxDim / (2 * Math.tan(fovRad))) * 1.8, controls.minDistance),
      controls.maxDistance,
    );

    // Position the camera on the correct side of the board based on where
    // the majority of target components sit. +Y = above (top face),
    // -Y = below (bottom face).
    const ySign = bottomCount > topCount ? -1 : 1;
    tweenStartPos.copy(camera.position);
    tweenEndPos.set(center.x, ySign * dist, center.z);
    tweenStartTarget.copy(controls.target);
    tweenEndTarget.copy(center);
    tweenProgress = 0;
    tweenActive = true;
  }

  // --- Animation loop ------------------------------------------------------

  let animFrameId = 0;
  let lastTime = performance.now();
  const animate = () => {
    animFrameId = requestAnimationFrame(animate);
    const now = performance.now();
    const dt = (now - lastTime) / 1000;
    lastTime = now;

    if (tweenActive) {
      tweenProgress = Math.min(tweenProgress + dt * TWEEN_SPEED, 1);
      const t = easeInOutCubic(tweenProgress);
      camera.position.lerpVectors(tweenStartPos, tweenEndPos, t);
      controls.target.lerpVectors(tweenStartTarget, tweenEndTarget, t);
      if (tweenProgress >= 1) tweenActive = false;
    }

    controls.update();
    renderer.render(scene, camera);
  };
  animate();

  // --- State + dispose -----------------------------------------------------

  const state: SceneState = {
    onSelect: null,
    setSideFilter: applySideFilter,
    setSelectedRef: applySelection,
    setHighlightedRefs: applyHighlightedRefs,
    setColorMode: applyColorMode,
    setTracesVisible: applyTracesVisible,
    focusOnRefs,
    dispose: () => {
      cancelAnimationFrame(animFrameId);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      renderer.domElement.removeEventListener('pointerup', onPointerUp);
      for (const g of ownedGeometries) g.dispose();
      for (const m of ownedMaterials) m.dispose();
      for (const t of ownedTextures) t.dispose();
      controls.dispose();
      renderer.dispose();
    },
  };

  return state;
}

// ---------------------------------------------------------------------------
// Component mesh builders
//
// Both variants return the same `BuildResult` shape so the main loop can
// uniformly track disposal. `primaryMaterial` is whichever MeshStandardMaterial
// receives the emissive highlight on selection.

interface BuildResult {
  root: THREE.Object3D;
  primaryMaterial: THREE.MeshStandardMaterial;
  geometries: THREE.BufferGeometry[];
  materials: THREE.Material[];
  textures: THREE.Texture[];
}

function buildBoxEntry(
  c: Component,
  widthMm: number,
  heightMm: number,
): BuildResult {
  // Floor the footprint extents so a degenerate (single-pad) bbox is still
  // visible at board scale; most real footprints clear this floor easily.
  const w = Math.max(c.footprintBbox.width, 0.5);
  const h = Math.max(c.footprintBbox.height, 0.5);
  const h3d = Math.max(c.footprintBbox.height3d, 0.3);
  const color = c.side === 'top' ? TOP_COLOR : BOTTOM_COLOR;

  const geom = new THREE.BoxGeometry(w, h3d, h);
  // Cloned per-component so the selection emissive doesn't bleed to siblings.
  const mat = new THREE.MeshStandardMaterial({ color, flatShading: true });
  const mesh = new THREE.Mesh(geom, mat);
  // Box is symmetric, so the center-of-box placement used in task #9 still
  // works — no inner/outer Group wrapping needed.
  mesh.position.set(
    c.x - widthMm / 2,
    c.side === 'top' ? BOARD_THICKNESS_MM + h3d / 2 : -h3d / 2,
    c.y - heightMm / 2,
  );
  mesh.rotation.y = -degToRad(c.rotation);
  mesh.userData = { ref: c.ref, side: c.side };

  return {
    root: mesh,
    primaryMaterial: mat,
    geometries: [geom],
    materials: [mat],
    textures: [],
  };
}

function buildHeroEntry(
  c: Component,
  widthMm: number,
  heightMm: number,
): BuildResult | null {
  if (!c.heroMeshId) return null;
  const hero = buildHeroMesh(c.heroMeshId, c);
  if (!hero) return null;

  // Nest so transforms compose in the right frame:
  //   world → outer (position + KiCad Y-rotation)
  //           → inner (optional X-flip for bottom-side mounting)
  //             → hero (local: +Y outward, origin at PCB face)
  // Hero meshes are authored with the PCB-touching face at y=0 and the
  // outward face (USB / label / AAA cells / SD slot) pointing +Y. For
  // bottom-side components the inner X-flip puts the outward face at -Y.
  const inner = new THREE.Group();
  inner.add(hero.object);
  if (c.side === 'bottom') inner.rotation.x = Math.PI;

  const outer = new THREE.Group();
  outer.add(inner);
  outer.position.set(
    c.x - widthMm / 2,
    c.side === 'top' ? BOARD_THICKNESS_MM : 0,
    c.y - heightMm / 2,
  );
  outer.rotation.y = -degToRad(c.rotation);
  outer.userData = { ref: c.ref, side: c.side };

  return {
    root: outer,
    primaryMaterial: hero.primaryMesh.material as THREE.MeshStandardMaterial,
    geometries: hero.ownedGeometries,
    materials: hero.ownedMaterials,
    textures: hero.ownedTextures,
  };
}

/**
 * Walk up from a raycaster hit until we find an object with `userData.ref`
 * set — that's the component root. Returns the ref string, or null if the
 * hit escaped into the scene root (shouldn't happen given we only ray
 * component roots, but stay defensive).
 */
function findRootRef(obj: THREE.Object3D): string | null {
  let cur: THREE.Object3D | null = obj;
  while (cur) {
    const ref = (cur.userData as { ref?: string }).ref;
    if (ref) return ref;
    cur = cur.parent;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Board outline → THREE.Shape
//
// Edge.Cuts arrive as a bag of line + arc segments in arbitrary order.
// Tessellate arcs to 16-segment polylines (chord error ≈ 0.03 mm at the
// typical 3 mm corner radius — imperceptible), greedy-chain them into rings,
// pick the longest ring as the outer boundary, and add mounting holes as
// inner paths with opposite winding.

function buildBoardShape(
  segments: EdgeSegment[],
  holes: Hole[],
  widthMm: number,
  heightMm: number,
): THREE.Shape | null {
  if (segments.length === 0) return null;

  const polylines: [number, number][][] = segments.map((seg) => {
    if (seg.kind === 'arc' && seg.points.length === 3) {
      return tessellateArc(
        seg.points[0] as [number, number],
        seg.points[1] as [number, number],
        seg.points[2] as [number, number],
        ARC_SEGMENTS,
      );
    }
    return seg.points.map(([x, y]) => [x, y]) as [number, number][];
  });

  const rings = chainPolylines(polylines);
  if (rings.length === 0) return null;

  // Longest ring wins as the outer boundary. In practice KiCad edges form
  // exactly one ring for the C1; anything else is a bug we want to see.
  rings.sort((a, b) => b.length - a.length);
  const outerKicad = rings[0];

  // Transform into shape coordinates — flip Y so KiCad's Y-down matches our
  // rendered orientation after the later -π/2 rotation around X.
  const outer: [number, number][] = outerKicad.map(([x, y]) => [
    x - widthMm / 2,
    heightMm / 2 - y,
  ]);

  // THREE.Shape expects a CCW outer ring (in its own 2D frame). Flip if the
  // greedy chain walked the other way.
  if (signedArea(outer) < 0) outer.reverse();

  const shape = new THREE.Shape();
  shape.moveTo(outer[0][0], outer[0][1]);
  for (let i = 1; i < outer.length; i++) {
    shape.lineTo(outer[i][0], outer[i][1]);
  }

  for (const hole of holes) {
    const cx = hole.x - widthMm / 2;
    const cy = heightMm / 2 - hole.y;
    const r = hole.diameter / 2;
    const path = new THREE.Path();
    // `clockwise = true` gives us an inner hole with opposite winding to
    // the CCW outer ring — ExtrudeGeometry punches through cleanly.
    path.absarc(cx, cy, r, 0, Math.PI * 2, true);
    shape.holes.push(path);
  }

  return shape;
}

// ---------------------------------------------------------------------------
// Silkscreen rasterization
//
// Both parsers emit line/arc/circle primitives in board-local mm coordinates
// (KiCad-style: origin top-left, Y grows down). We rasterize them onto a
// `widthMm*PX × heightMm*PX` canvas at SILK_PX_PER_MM, wrap in a CanvasTexture,
// and overlay via a transparent PlaneGeometry just above/below the board face.
//
// Y mapping differs per face because of the PlaneGeometry + X-rotation combo:
//   Top plane    (rot.x = -π/2): plane +Y → world -Z → KiCad y=0 (board top).
//                So UV v=1 (canvas row 0) needs to show KiCad y=0.
//                → canvas_y = kicad_y * PX_PER_MM.
//   Bottom plane (rot.x = +π/2): plane +Y → world +Z → KiCad y=heightMm.
//                So UV v=1 (canvas row 0) needs to show KiCad y=heightMm.
//                → canvas_y = (heightMm - kicad_y) * PX_PER_MM.
// Texture `flipY` stays at the default `true` throughout.

interface SilkscreenOverlay {
  mesh: THREE.Mesh;
  geometry: THREE.PlaneGeometry;
  material: THREE.MeshBasicMaterial;
  texture: THREE.CanvasTexture;
}

function buildSilkscreenOverlay(
  layer: SilkscreenLayer,
  widthMm: number,
  heightMm: number,
  face: 'top' | 'bottom',
  boardThickness: number,
): SilkscreenOverlay | null {
  if (
    layer.lines.length === 0 &&
    layer.arcs.length === 0 &&
    layer.circles.length === 0
  ) {
    return null;
  }

  const texture = rasterizeSilkscreen(layer, widthMm, heightMm, face);
  const geometry = new THREE.PlaneGeometry(widthMm, heightMm);
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    // Silk is a decal on top of the board. Writing depth would cause it to
    // occlude hero-mesh castellation nubs sitting right at the board surface.
    depthWrite: false,
  });
  const mesh = new THREE.Mesh(geometry, material);

  if (face === 'top') {
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = boardThickness + SILK_Y_OFFSET_MM;
  } else {
    mesh.rotation.x = Math.PI / 2;
    mesh.position.y = -SILK_Y_OFFSET_MM;
  }

  return { mesh, geometry, material, texture };
}

function rasterizeSilkscreen(
  layer: SilkscreenLayer,
  widthMm: number,
  heightMm: number,
  face: 'top' | 'bottom',
): THREE.CanvasTexture {
  const w = Math.max(1, Math.ceil(widthMm * SILK_PX_PER_MM));
  const h = Math.max(1, Math.ceil(heightMm * SILK_PX_PER_MM));

  // Safari pre-16.4 lacks OffscreenCanvas; fall back to a detached HTMLCanvas.
  const canvas: OffscreenCanvas | HTMLCanvasElement =
    typeof OffscreenCanvas !== 'undefined'
      ? new OffscreenCanvas(w, h)
      : Object.assign(document.createElement('canvas'), {
          width: w,
          height: h,
        });
  const ctx = canvas.getContext('2d') as
    | OffscreenCanvasRenderingContext2D
    | CanvasRenderingContext2D
    | null;
  if (!ctx) {
    // Caller bails on an empty texture — extremely unlikely in practice.
    return new THREE.CanvasTexture(canvas as HTMLCanvasElement);
  }

  ctx.strokeStyle = SILK_COLOR;
  ctx.lineWidth = SILK_LINE_MM * SILK_PX_PER_MM;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  const toCanvas = (x: number, y: number): [number, number] => [
    x * SILK_PX_PER_MM,
    (face === 'top' ? y : heightMm - y) * SILK_PX_PER_MM,
  ];

  for (const line of layer.lines) {
    const [x1, y1] = toCanvas(line.start[0], line.start[1]);
    const [x2, y2] = toCanvas(line.end[0], line.end[1]);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  for (const arc of layer.arcs) {
    const pts = tessellateArc(arc.start, arc.mid, arc.end, ARC_SEGMENTS);
    if (pts.length < 2) continue;
    ctx.beginPath();
    const [sx, sy] = toCanvas(pts[0][0], pts[0][1]);
    ctx.moveTo(sx, sy);
    for (let i = 1; i < pts.length; i++) {
      const [px, py] = toCanvas(pts[i][0], pts[i][1]);
      ctx.lineTo(px, py);
    }
    ctx.stroke();
  }

  for (const circle of layer.circles) {
    const [cx, cy] = toCanvas(circle.center[0], circle.center[1]);
    ctx.beginPath();
    ctx.arc(cx, cy, circle.radius * SILK_PX_PER_MM, 0, Math.PI * 2);
    ctx.stroke();
  }

  const texture = new THREE.CanvasTexture(canvas as HTMLCanvasElement);
  texture.needsUpdate = true;
  return texture;
}

// ---------------------------------------------------------------------------
// Copper trace + via mesh builders (task #13f)

interface TraceLinesResult {
  mesh: THREE.LineSegments;
  geometry: THREE.BufferGeometry;
  material: THREE.LineBasicMaterial;
}

function buildTraceLines(
  traces: CopperSegment[],
  widthMm: number,
  heightMm: number,
  layer: CopperLayer,
  boardThickness: number,
): TraceLinesResult {
  // Each trace is a pair of vertices in XZ plane (board coordinates).
  const positions = new Float32Array(traces.length * 6);
  for (let i = 0; i < traces.length; i++) {
    const t = traces[i];
    const off = i * 6;
    positions[off + 0] = t.start[0] - widthMm / 2;
    positions[off + 1] = 0; // Y set below via mesh position
    positions[off + 2] = t.start[1] - heightMm / 2;
    positions[off + 3] = t.end[0] - widthMm / 2;
    positions[off + 4] = 0;
    positions[off + 5] = t.end[1] - heightMm / 2;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

  const color = layer === 'f-cu' ? TRACE_TOP_COLOR : TRACE_BOTTOM_COLOR;
  const material = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity: 0.85,
    depthWrite: false,
  });

  const mesh = new THREE.LineSegments(geometry, material);
  mesh.position.y =
    layer === 'f-cu'
      ? boardThickness + TRACE_Y_OFFSET_MM
      : -TRACE_Y_OFFSET_MM;

  return { mesh, geometry, material };
}

interface ViasResult {
  mesh: THREE.Group;
  geometry: THREE.CylinderGeometry;
  material: THREE.MeshStandardMaterial;
}

function buildVias(
  vias: Via[],
  widthMm: number,
  heightMm: number,
  boardThickness: number,
): ViasResult {
  // Shared geometry + material for all vias. Each via is an individual Mesh
  // positioned at its (x, z) with the cylinder spanning the full board depth
  // plus a tiny extension so they poke above/below.
  const representativeRadius = vias.length > 0 ? vias[0].diameter / 2 : 0.3;
  const height = boardThickness * 1.02;
  const geometry = new THREE.CylinderGeometry(
    representativeRadius,
    representativeRadius,
    height,
    VIA_SEGMENTS,
  );
  const material = new THREE.MeshStandardMaterial({
    color: VIA_COLOR,
    metalness: 0.6,
    roughness: 0.3,
    transparent: true,
    opacity: 0.9,
    depthWrite: false,
  });

  const group = new THREE.Group();
  for (const v of vias) {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(
      v.at[0] - widthMm / 2,
      boardThickness / 2, // center the cylinder in the board
      v.at[1] - heightMm / 2,
    );
    group.add(mesh);
  }

  return { mesh: group, geometry, material };
}

// ---------------------------------------------------------------------------
// Helpers

function degToRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

/**
 * Tessellate a KiCad three-point arc (start, mid, end) into a polyline of
 * `segments + 1` points along the circumcircle, preserving the side of the
 * arc the `mid` point marks. Falls back to a straight line if the three
 * points are collinear.
 */
function tessellateArc(
  start: [number, number],
  mid: [number, number],
  end: [number, number],
  segments: number,
): [number, number][] {
  const [ax, ay] = start;
  const [bx, by] = mid;
  const [cx, cy] = end;

  const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
  if (Math.abs(d) < 1e-9) {
    return [start, end];
  }
  const a2 = ax * ax + ay * ay;
  const b2 = bx * bx + by * by;
  const c2 = cx * cx + cy * cy;
  const ox = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d;
  const oy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d;
  const r = Math.hypot(ax - ox, ay - oy);

  const startAng = Math.atan2(ay - oy, ax - ox);
  const midAng = Math.atan2(by - oy, bx - ox);
  const endAng = Math.atan2(cy - oy, cx - ox);

  // Normalize angles relative to startAng in the [0, 2π) range walking CCW.
  const norm = (a: number): number => {
    let x = a - startAng;
    while (x < 0) x += Math.PI * 2;
    while (x >= Math.PI * 2) x -= Math.PI * 2;
    return x;
  };
  const midRel = norm(midAng);
  const endRel = norm(endAng);
  // If mid comes before end walking CCW from start, we're sweeping CCW.
  // Otherwise we need the negative sweep (CW short arc).
  const sweep = midRel < endRel ? endRel : endRel - Math.PI * 2;

  const points: [number, number][] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const a = startAng + sweep * t;
    points.push([ox + r * Math.cos(a), oy + r * Math.sin(a)]);
  }
  return points;
}

/**
 * Greedy-chain a set of polylines into rings by matching endpoints.
 * Same algorithm as the old SVG outline builder; fresh implementation in
 * point-array form. Stragglers that don't close are returned as-is — the
 * caller picks the largest ring.
 */
function chainPolylines(polylines: [number, number][][]): [number, number][][] {
  const eps = 1e-3;
  const pointsEqual = (a: [number, number], b: [number, number]) =>
    Math.abs(a[0] - b[0]) < eps && Math.abs(a[1] - b[1]) < eps;

  const remaining = polylines.map((p) => p.slice() as [number, number][]);
  const consumed = new Array(remaining.length).fill(false);
  const rings: [number, number][][] = [];

  for (;;) {
    const startIdx = consumed.findIndex((c) => !c);
    if (startIdx === -1) break;
    consumed[startIdx] = true;
    const chain: [number, number][] = remaining[startIdx].slice();

    let extended = true;
    while (extended) {
      extended = false;
      for (let i = 0; i < remaining.length; i++) {
        if (consumed[i]) continue;
        const seg = remaining[i];
        const head = chain[chain.length - 1];
        const tail = chain[0];
        if (pointsEqual(head, seg[0])) {
          for (let j = 1; j < seg.length; j++) chain.push(seg[j]);
          consumed[i] = true;
          extended = true;
        } else if (pointsEqual(head, seg[seg.length - 1])) {
          for (let j = seg.length - 2; j >= 0; j--) chain.push(seg[j]);
          consumed[i] = true;
          extended = true;
        } else if (pointsEqual(tail, seg[seg.length - 1])) {
          for (let j = seg.length - 2; j >= 0; j--) chain.unshift(seg[j]);
          consumed[i] = true;
          extended = true;
        } else if (pointsEqual(tail, seg[0])) {
          for (let j = 1; j < seg.length; j++) chain.unshift(seg[j]);
          consumed[i] = true;
          extended = true;
        }
      }
    }

    rings.push(chain);
  }
  return rings;
}

/** Standard shoelace formula. Positive = CCW in standard math orientation. */
function signedArea(points: [number, number][]): number {
  let sum = 0;
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % points.length];
    sum += x1 * y2 - x2 * y1;
  }
  return sum / 2;
}
