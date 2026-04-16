import { useMemo, useState } from 'react';
import { useDataset } from '../lib/dataset-context';
import type {
  BoardData, BoardId, BomLine, Component, EdgeSegment,
} from '../lib/types';

const BOARDS: { id: BoardId; label: string }[] = [
  { id: 'c1-main', label: 'C1 main' },
  { id: 'c2-driver', label: 'C2 driver' },
];

type SideFilter = 'both' | 'top' | 'bottom';
const SIDE_FILTERS: { id: SideFilter; label: string }[] = [
  { id: 'both', label: 'Both sides' },
  { id: 'top', label: 'Top' },
  { id: 'bottom', label: 'Bottom' },
];

const MARGIN_MM = 5;
const TOP_FILL = '#f59e0b';
const BOTTOM_FILL = '#38bdf8';
const BOARD_FILL = '#1e293b';
const BOARD_STROKE = '#475569';
const HOLE_FILL = '#0f172a';

export function BoardView() {
  const dataset = useDataset();
  const [board, setBoard] = useState<BoardId>('c1-main');
  const [sideFilter, setSideFilter] = useState<SideFilter>('both');
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const boardData = dataset.boards[board];
  const visible = useMemo(
    () => boardData.components.filter(
      (c) => sideFilter === 'both' || c.side === sideFilter,
    ),
    [boardData.components, sideFilter],
  );

  const selected = useMemo(
    () => (selectedRef ? boardData.components.find((c) => c.ref === selectedRef) ?? null : null),
    [boardData.components, selectedRef],
  );

  // Reset selection when switching boards so a stale C1 ref doesn't bleed
  // into the (currently empty) C2 view.
  const handleBoardChange = (next: BoardId) => {
    setBoard(next);
    setSelectedRef(null);
  };

  return (
    <div style={{ display: 'flex', gap: '16px', height: '100%' }}>
      <section style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Toolbar
          board={board}
          setBoard={handleBoardChange}
          sideFilter={sideFilter}
          setSideFilter={setSideFilter}
          componentCount={boardData.components.length}
          holeCount={boardData.outline.holes.length}
        />
        {boardData.components.length === 0 && boardData.outline.edgeSegments.length === 0 ? (
          <EmptyBoard board={board} />
        ) : (
          <BoardSvg
            data={boardData}
            visible={visible}
            selectedRef={selectedRef}
            onSelect={setSelectedRef}
          />
        )}
      </section>

      <aside style={{
        width: '340px',
        flexShrink: 0,
        borderLeft: '1px solid #334155',
        paddingLeft: '16px',
        overflow: 'auto',
      }}>
        {selected ? (
          <DetailPanel component={selected} bom={dataset.bom} />
        ) : (
          <DetailPlaceholder />
        )}
      </aside>
    </div>
  );
}

function Toolbar({
  board, setBoard, sideFilter, setSideFilter, componentCount, holeCount,
}: {
  board: BoardId;
  setBoard: (b: BoardId) => void;
  sideFilter: SideFilter;
  setSideFilter: (s: SideFilter) => void;
  componentCount: number;
  holeCount: number;
}) {
  return (
    <div style={{
      display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap',
      paddingBottom: '12px', borderBottom: '1px solid #334155', marginBottom: '8px',
    }}>
      <div style={{ display: 'flex', gap: '4px' }}>
        {BOARDS.map((b) => (
          <button
            key={b.id}
            onClick={() => setBoard(b.id)}
            style={pillStyle(b.id === board)}
          >
            {b.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '4px' }}>
        {SIDE_FILTERS.map((s) => (
          <button
            key={s.id}
            onClick={() => setSideFilter(s.id)}
            style={pillStyle(s.id === sideFilter)}
          >
            {s.label}
          </button>
        ))}
      </div>

      <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#64748b' }}>
        {componentCount} components · {holeCount} mounting holes
      </span>
    </div>
  );
}

function pillStyle(active: boolean): React.CSSProperties {
  return {
    padding: '4px 10px', fontSize: '11px',
    background: active ? '#334155' : 'transparent',
    color: '#e2e8f0',
    border: '1px solid ' + (active ? '#475569' : '#334155'),
    borderRadius: '4px', cursor: 'pointer',
  };
}

function BoardSvg({
  data, visible, selectedRef, onSelect,
}: {
  data: BoardData;
  visible: Component[];
  selectedRef: string | null;
  onSelect: (ref: string | null) => void;
}) {
  const { widthMm, heightMm, edgeSegments, holes } = data.outline;
  const outlinePath = useMemo(() => buildOutlinePath(edgeSegments), [edgeSegments]);

  // Fit-to-viewport: a constant margin on all sides so corner arcs aren't
  // clipped. The parent flexbox sizes the <svg> element.
  const viewBox = [
    -MARGIN_MM, -MARGIN_MM,
    widthMm + 2 * MARGIN_MM, heightMm + 2 * MARGIN_MM,
  ].join(' ');

  return (
    <div style={{
      flex: 1, border: '1px solid #1e293b', borderRadius: '6px',
      background: '#0b1220', padding: '8px', minHeight: 0,
      display: 'flex',
    }}>
      <svg
        viewBox={viewBox}
        preserveAspectRatio="xMidYMid meet"
        style={{ width: '100%', height: '100%', cursor: 'default' }}
        onClick={(e) => {
          // Click on empty SVG area clears selection; component clicks
          // stopPropagation so they survive.
          if (e.target === e.currentTarget) onSelect(null);
        }}
      >
        {/* Board outline (rounded rect from Edge.Cuts) */}
        {outlinePath && (
          <path d={outlinePath} fill={BOARD_FILL} stroke={BOARD_STROKE} strokeWidth={0.3} />
        )}

        {/* Mounting holes */}
        {holes.map((h, i) => (
          <circle
            key={`hole-${i}`}
            cx={h.x} cy={h.y} r={h.diameter / 2}
            fill={HOLE_FILL} stroke={BOARD_STROKE} strokeWidth={0.15}
          />
        ))}

        {/* Components */}
        {visible.map((c) => (
          <ComponentGlyph
            key={c.ref}
            component={c}
            selected={c.ref === selectedRef}
            onClick={() => onSelect(c.ref)}
          />
        ))}
      </svg>
    </div>
  );
}

function ComponentGlyph({
  component, selected, onClick,
}: {
  component: Component;
  selected: boolean;
  onClick: () => void;
}) {
  const { x, y, rotation, side, footprintBbox, ref } = component;
  // Clamp tiny bboxes to a minimum size so single-pad placements are still
  // visible at board scale. Most footprints are well above this floor.
  const w = Math.max(footprintBbox.width, 1.0);
  const h = Math.max(footprintBbox.height, 1.0);
  const fill = side === 'top' ? TOP_FILL : BOTTOM_FILL;
  const opacity = selected ? 1.0 : 0.75;
  const stroke = selected ? '#f8fafc' : 'rgba(15, 23, 42, 0.6)';
  const strokeWidth = selected ? 0.35 : 0.1;
  // SVG label size in mm — fits inside most footprints without scaling with
  // bbox (keeps labels legible across varied part sizes).
  const labelSize = Math.max(0.8, Math.min(2.2, Math.min(w, h) * 0.5));

  return (
    <g
      transform={`translate(${x} ${y}) rotate(${rotation})`}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      style={{ cursor: 'pointer' }}
    >
      <rect
        x={-w / 2} y={-h / 2} width={w} height={h}
        fill={fill} opacity={opacity} stroke={stroke} strokeWidth={strokeWidth}
        rx={0.2} ry={0.2}
      />
      <text
        x={0} y={0}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={labelSize}
        fill="#0f172a"
        style={{ pointerEvents: 'none', userSelect: 'none', fontFamily: 'monospace', fontWeight: 600 }}
      >
        {ref}
      </text>
    </g>
  );
}

/**
 * Build a single SVG `<path>` from KiCad edge segments. Arcs are tessellated
 * as two straight-line segments through (start → mid → end); at board-corner
 * radii (~3 mm) the visual difference vs. a real arc is negligible and it
 * sidesteps three-point-arc → SVG-A-command math for the v1 preview.
 *
 * KiCad edges arrive in arbitrary order, so we greedy-chain: start with the
 * first segment, then repeatedly find a segment whose endpoint matches the
 * current chain's tail and extend. Any stragglers are drawn as `M ... L ...`
 * subpaths so nothing is silently dropped.
 */
function buildOutlinePath(segments: EdgeSegment[]): string {
  if (segments.length === 0) return '';
  const remaining = segments.map((s) => s.points.slice() as [number, number][]);
  const consumed = new Array(remaining.length).fill(false);
  const parts: string[] = [];
  const eps = 1e-3;

  const pointsEqual = (a: [number, number], b: [number, number]) =>
    Math.abs(a[0] - b[0]) < eps && Math.abs(a[1] - b[1]) < eps;

  while (true) {
    const startIdx = consumed.findIndex((c) => !c);
    if (startIdx === -1) break;
    consumed[startIdx] = true;
    const chain: [number, number][] = remaining[startIdx].slice() as [number, number][];

    // Extend forward (and implicitly backward by reversing mid-loop).
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
          consumed[i] = true; extended = true;
        } else if (pointsEqual(head, seg[seg.length - 1])) {
          for (let j = seg.length - 2; j >= 0; j--) chain.push(seg[j]);
          consumed[i] = true; extended = true;
        } else if (pointsEqual(tail, seg[seg.length - 1])) {
          for (let j = seg.length - 2; j >= 0; j--) chain.unshift(seg[j]);
          consumed[i] = true; extended = true;
        } else if (pointsEqual(tail, seg[0])) {
          for (let j = 1; j < seg.length; j++) chain.unshift(seg[j]);
          consumed[i] = true; extended = true;
        }
      }
    }

    const [x0, y0] = chain[0];
    let d = `M ${x0} ${y0}`;
    for (let i = 1; i < chain.length; i++) {
      d += ` L ${chain[i][0]} ${chain[i][1]}`;
    }
    // Close the subpath if it's a ring.
    if (pointsEqual(chain[0], chain[chain.length - 1])) {
      d += ' Z';
    }
    parts.push(d);
  }

  return parts.join(' ');
}

function DetailPanel({ component, bom }: { component: Component; bom: BomLine[] }) {
  const line = useMemo(
    () => bom.find((b) => b.refs.includes(component.bomRef)) ?? null,
    [bom, component.bomRef],
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '12px', color: '#e2e8f0' }}>
      <header style={{ display: 'flex', gap: '8px', alignItems: 'baseline', flexWrap: 'wrap' }}>
        <h2 style={{ fontSize: '14px', color: '#f1f5f9', margin: 0 }}>
          {component.ref}
        </h2>
        <SidePill side={component.side} />
      </header>

      {line ? (
        <div style={{ color: '#cbd5e1', lineHeight: 1.45 }}>{line.function}</div>
      ) : (
        <div style={{ color: '#fbbf24', fontStyle: 'italic' }}>
          No BOM entry matches {component.bomRef}.
        </div>
      )}

      <Field
        label="Position"
        value={
          <span style={{ fontFamily: 'monospace' }}>
            ({component.x.toFixed(2)}, {component.y.toFixed(2)}) mm · {component.rotation}°
          </span>
        }
      />
      <Field label="Footprint" value={<span style={{ fontFamily: 'monospace' }}>{component.footprint}</span>} />
      <Field
        label="Bbox"
        value={
          <span style={{ fontFamily: 'monospace' }}>
            {component.footprintBbox.width.toFixed(2)} × {component.footprintBbox.height.toFixed(2)} mm
          </span>
        }
      />
      <Field label="Pads" value={String(component.pads.length)} />

      {line && (
        <>
          <Field label="MPN" value={<span style={{ fontFamily: 'monospace' }}>{line.mpn}</span>} />
          {line.manufacturer && <Field label="Manufacturer" value={line.manufacturer} />}
          <Field label="Unit cost" value={line.unitCostUsd !== undefined ? `$${line.unitCostUsd.toFixed(2)}` : '—'} />
          {line.digikeyPn && (
            <Field label="Digi-Key" value={<span style={{ fontFamily: 'monospace' }}>{line.digikeyPn}</span>} />
          )}
          {line.datasheetUrl && (
            <Field
              label="Datasheet"
              value={
                <a
                  href={line.datasheetUrl}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: '#60a5fa', textDecoration: 'none' }}
                >
                  {line.datasheetUrl}
                </a>
              }
            />
          )}
        </>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: '8px' }}>
      <span style={{ width: '110px', color: '#64748b', flexShrink: 0 }}>{label}</span>
      <span style={{ color: '#e2e8f0', wordBreak: 'break-word', minWidth: 0 }}>{value}</span>
    </div>
  );
}

function DetailPlaceholder() {
  return (
    <div style={{
      padding: '24px 8px', color: '#64748b', fontSize: '12px',
      fontStyle: 'italic', lineHeight: 1.5,
    }}>
      Click a component on the board to see its position, footprint, and BOM
      metadata. A proper 3D viewport lands in task #9.
    </div>
  );
}

function SidePill({ side }: { side: 'top' | 'bottom' }) {
  return (
    <span style={{
      padding: '2px 6px', fontSize: '10px',
      background: side === 'top' ? '#78350f' : '#075985',
      color: side === 'top' ? '#fef3c7' : '#cffafe',
      borderRadius: '3px',
      letterSpacing: '0.3px',
    }}>
      {side.toUpperCase()}
    </span>
  );
}

function EmptyBoard({ board }: { board: BoardId }) {
  const message = board === 'c2-driver'
    ? 'C2 driver geometry lands in task #11 (EAGLE parser).'
    : 'No board geometry available yet.';
  return (
    <div style={{
      flex: 1,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#64748b', fontSize: '13px', fontStyle: 'italic',
      border: '1px dashed #334155', borderRadius: '8px',
    }}>
      {message}
    </div>
  );
}
