import { useMemo, useState } from 'react';
import { useDataset } from '../lib/dataset-context';
import { useNavigation } from '../lib/navigation-context';
import { BoardViewport } from './BoardViewport';
import type { ColorMode } from '../lib/scene-renderer';
import type { BoardId, BomLine, Component } from '../lib/types';

const BOARDS: { id: BoardId; label: string }[] = [
  { id: 'c1-main', label: 'Main Board' },
  { id: 'c2-driver', label: 'E-Paper Driver' },
];

type SideFilter = 'both' | 'top' | 'bottom';
const SIDE_FILTERS: { id: SideFilter; label: string }[] = [
  { id: 'both', label: 'Both sides' },
  { id: 'top', label: 'Top' },
  { id: 'bottom', label: 'Bottom' },
];

export function BoardView() {
  const dataset = useDataset();
  const { board, setBoard, selectedRef, selectComponent } = useNavigation();
  const [sideFilter, setSideFilter] = useState<SideFilter>('both');
  const [colorMode, setColorMode] = useState<ColorMode>('side');
  const [showTraces, setShowTraces] = useState(false);

  const boardData = dataset.boards[board];

  const selected = useMemo(
    () => (selectedRef ? boardData.components.find((c) => c.ref === selectedRef) ?? null : null),
    [boardData.components, selectedRef],
  );

  // Reset selection when switching boards so a stale C1 ref doesn't bleed
  // into the C2 view (and vice versa).
  const handleBoardChange = (next: BoardId) => {
    setBoard(next);
    selectComponent(null);
  };

  const hasGeometry =
    boardData.components.length > 0 || boardData.outline.edgeSegments.length > 0;

  return (
    <div style={{ display: 'flex', gap: '16px', height: '100%' }}>
      <section style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Toolbar
          board={board}
          setBoard={handleBoardChange}
          sideFilter={sideFilter}
          setSideFilter={setSideFilter}
          colorMode={colorMode}
          setColorMode={setColorMode}
          showTraces={showTraces}
          setShowTraces={setShowTraces}
          componentCount={boardData.components.length}
          holeCount={boardData.outline.holes.length}
        />
        {hasGeometry ? (
          <BoardViewport
            boardData={boardData}
            sideFilter={sideFilter}
            selectedRef={selectedRef}
            onSelect={selectComponent}
            colorMode={colorMode}
            showTraces={showTraces}
          />
        ) : (
          <EmptyBoard board={board} />
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

const COLOR_MODES: { id: ColorMode; label: string }[] = [
  { id: 'side', label: 'Board Side' },
  { id: 'netCategory', label: 'Signal Type' },
];

function Toolbar({
  board, setBoard, sideFilter, setSideFilter, colorMode, setColorMode,
  showTraces, setShowTraces, componentCount, holeCount,
}: {
  board: BoardId;
  setBoard: (b: BoardId) => void;
  sideFilter: SideFilter;
  setSideFilter: (s: SideFilter) => void;
  colorMode: ColorMode;
  setColorMode: (m: ColorMode) => void;
  showTraces: boolean;
  setShowTraces: (v: boolean) => void;
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

      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
        <span style={{ fontSize: '10px', color: '#64748b', marginRight: '2px' }}>Color by:</span>
        {COLOR_MODES.map((m) => (
          <button
            key={m.id}
            onClick={() => setColorMode(m.id)}
            style={pillStyle(m.id === colorMode)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <label style={{ display: 'flex', gap: '4px', alignItems: 'center', fontSize: '10px', color: '#64748b', cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={showTraces}
          onChange={(e) => setShowTraces(e.target.checked)}
          style={{ accentColor: '#f59e0b' }}
        />
        Copper Traces
      </label>

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
      <Field label="PCB Footprint" value={<span style={{ fontFamily: 'monospace' }}>{component.footprint}</span>} />
      <Field
        label="Dimensions"
        value={
          <span style={{ fontFamily: 'monospace' }}>
            {component.footprintBbox.width.toFixed(2)} × {component.footprintBbox.height.toFixed(2)} × {component.footprintBbox.height3d.toFixed(2)} mm
          </span>
        }
      />
      <Field label="Solder Points" value={String(component.pads.length)} />
      {component.dominantCategory && (
        <Field label="Signal Type" value={component.dominantCategory} />
      )}

      {line && (
        <>
          <Field label="Part Number" value={<span style={{ fontFamily: 'monospace' }}>{line.mpn}</span>} />
          {line.manufacturer && <Field label="Manufacturer" value={line.manufacturer} />}
          <Field label="Unit cost" value={line.unitCostUsd !== undefined ? `$${line.unitCostUsd.toFixed(2)}` : '—'} />
          {line.digikeyPn && (
            <Field label="Digi-Key PN" value={<span style={{ fontFamily: 'monospace' }}>{line.digikeyPn}</span>} />
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
                  View Datasheet
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
      Click a component in the 3D viewport to see its position, footprint,
      and part details. Drag to orbit, scroll to zoom.
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

function EmptyBoard({ board: _board }: { board: BoardId }) {
  // With both C1 (KiCad) and C2 (EAGLE) parsers wired up, this branch only
  // fires if a parser misses the outline — the message stays generic rather
  // than pinning to a specific board.
  const message = 'No board geometry available yet.';
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
