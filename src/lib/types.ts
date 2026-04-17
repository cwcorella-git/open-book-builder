// Types mirror `src-tauri/src/types.rs`. Keep them in sync.

export type Side = 'top' | 'bottom';
export type BoardId = 'c1-main' | 'c2-driver';

export type NetCategory =
  | 'power' | 'ground' | 'spi' | 'i2c' | 'gpio' | 'debug' | 'analog' | 'other';

export type Severity =
  | 'build-critical' | 'cost-impact' | 'naming' | 'informational';

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
}

export interface Discrepancy {
  id: string;
  severity: Severity;
  title: string;
  description: string;
  sources: string[];
  affectsComponents: string[];
  resolution: string;
}

export interface BomComparison {
  bomRef: string;
  canonicalQty: number;
  canonicalCost?: number;
  cogsQty?: number;
  cogsCost?: number;
  pdfQty?: number;
  pdfCost?: number;
  april2025Qty?: number;
  april2025Cost?: number;
  conflict: boolean;
  note?: string;
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
  perTenUnitsUsd: number;
  missingLineItems: string[];
}

export interface BoardDataset {
  boards: Record<BoardId, BoardData>;
  bom: BomLine[];
  bomComparison: BomComparison[];
  discrepancies: Discrepancy[];
  assembly: AssemblyStep[];
  costSummary: CostSummary;
}
