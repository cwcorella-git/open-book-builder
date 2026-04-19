// Types mirror `src-tauri/src/types.rs`. Keep them in sync.

export type Side = 'top' | 'bottom';
export type BoardId = 'c1-main' | 'c2-driver';

export type NetCategory =
  | 'power' | 'ground' | 'spi' | 'i2c' | 'gpio' | 'debug' | 'analog' | 'other';

export type AssemblyPhase =
  | 'smd-passives' | 'smd-ics' | 'smd-mechanical'
  | 'tht' | 'modules' | 'mechanical' | 'flash-firmware';

export interface BomLine {
  refs: string[];
  qty: number;
  description: string;
  manufacturer?: string;
  mpn: string;
  digikeyPn?: string;
  mouserPn?: string;
  lcscPn?: string;
  optional: boolean;
  unitCostUsd?: number;
  livePrice?: number;
  footprint?: string;
  function: string;
  datasheetUrl?: string;
  heroMeshId?: string;
  board: BoardId;
}

export interface FootprintBbox {
  width: number;
  height: number;
  height3d: number;
}

export interface Pad {
  number: string;
  x: number;
  y: number;
  shape: string;
  size: [number, number];
  netName?: string;
  throughHole: boolean;
}

export interface Component {
  ref: string;
  bomRef: string;
  x: number;
  y: number;
  rotation: number;
  side: Side;
  footprint: string;
  footprintBbox: FootprintBbox;
  pads: Pad[];
  heroMeshId?: string;
  dominantCategory?: NetCategory;
  board: BoardId;
}

export interface NetPadRef {
  ref: string;
  pad: string;
  board: BoardId;
}

export interface Net {
  name: string;
  category: NetCategory;
  connectedPads: NetPadRef[];
}

export interface Hole {
  x: number;
  y: number;
  diameter: number;
}

export interface EdgeSegment {
  kind: 'line' | 'arc' | string;
  points: [number, number][];
}

// Copper trace segments and vias. Parsed from KiCad (segment)/(via) and EAGLE
// <signal>/<wire>/<via>. Rendered as LineSegments per layer + CylinderGeometry
// per via behind a "Show traces" toggle (default off).

export type CopperLayer = 'f-cu' | 'b-cu';

export interface CopperSegment {
  start: [number, number];
  end: [number, number];
  width: number;
  layer: CopperLayer;
  netName?: string;
}

export interface Via {
  at: [number, number];
  diameter: number;
  netName?: string;
}

// Board-space silkscreen primitives keyed by face. Lines / arcs / circles only;
// text glyphs and polygon fills are out of scope for task #13a. Matches the
// Rust `SilkscreenLayer` shape (camelCase on the wire).
export interface SilkscreenLine {
  start: [number, number];
  end: [number, number];
}

export interface SilkscreenArc {
  start: [number, number];
  mid: [number, number];
  end: [number, number];
}

export interface SilkscreenCircle {
  center: [number, number];
  radius: number;
}

export interface SilkscreenLayer {
  lines: SilkscreenLine[];
  arcs: SilkscreenArc[];
  circles: SilkscreenCircle[];
}

export interface BoardOutline {
  widthMm: number;
  heightMm: number;
  holes: Hole[];
  edgeSegments: EdgeSegment[];
  silkscreenTop: SilkscreenLayer;
  silkscreenBottom: SilkscreenLayer;
}

export interface BoardData {
  components: Component[];
  outline: BoardOutline;
  nets: Net[];
  traces: CopperSegment[];
  vias: Via[];
}

export interface AssemblyStep {
  id: string;
  order: number;
  phase: AssemblyPhase;
  title: string;
  description: string;
  componentRefs: string[];
  board: BoardId;
  estimatedMinutes?: number;
  tools: string[];
  notes?: string;
}

export interface CostSummary {
  perUnitUsd: number;
  missingLineItems: string[];
}

export interface BoardDataset {
  boards: Record<BoardId, BoardData>;
  bom: BomLine[];
  assembly: AssemblyStep[];
  costSummary: CostSummary;
}
