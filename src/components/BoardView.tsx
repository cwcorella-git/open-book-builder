// Board tab — detail panel for the selected component. The 3D viewport and
// toolbar now live in the persistent ViewportColumn (App.tsx). This component
// just shows the component info when something is clicked.

import { useEffect, useMemo, useRef, useState } from 'react';
import { useDataset } from '../lib/dataset-context';
import { useNavigation } from '../lib/navigation-context';
import { useViewport } from '../lib/viewport-context';
import { useBreakpoint } from '../lib/use-breakpoint';
import { BoardViewport } from './BoardViewport';
import type { BoardId, BomLine, Component } from '../lib/types';
import type { SideFilter } from '../lib/scene-renderer';

const BOARDS: { id: BoardId; label: string }[] = [
  { id: 'c1-main', label: 'Main' },
  { id: 'c2-driver', label: 'Driver' },
];

const SIDE_FILTERS: { id: SideFilter; label: string }[] = [
  { id: 'both', label: 'All' },
  { id: 'top', label: 'Top' },
  { id: 'bottom', label: 'Bottom' },
];

export function BoardView() {
  const dataset = useDataset();
  const { board, setBoard, selectedRef, selectComponent } = useNavigation();
  const { setConfig } = useViewport();
  const bp = useBreakpoint();
  const compact = bp === 'compact';

  // Mobile-only local state for the inline viewport.
  const [sideFilter, setSideFilter] = useState<SideFilter>('both');

  const boardData = dataset.boards[board];

  const selected = useMemo(
    () => (selectedRef ? boardData.components.find((c) => c.ref === selectedRef) ?? null : null),
    [boardData.components, selectedRef],
  );

  // Tab activation: enable click-to-select, clear any Assembly highlights.
  useEffect(() => {
    setConfig({ clickSelectEnabled: true, highlightedRefs: null, visible: true });
  }, [setConfig]);

  // Focus camera on newly selected component (desktop persistent viewport).
  const prevRef = useRef<string | null>(null);
  useEffect(() => {
    if (selectedRef && selectedRef !== prevRef.current) {
      setConfig({ focusRefs: [selectedRef] });
    }
    prevRef.current = selectedRef;
  }, [selectedRef, setConfig]);

  if (compact) {
    // On mobile the persistent viewport column is hidden, so we render an
    // inline viewport here. Tapping a component shows the detail panel below.
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <MobileToolbar
          board={board}
          setBoard={setBoard}
          sideFilter={sideFilter}
          setSideFilter={setSideFilter}
        />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '200px' }}>
          <BoardViewport
            boardData={boardData}
            sideFilter={sideFilter}
            selectedRef={selectedRef}
            onSelect={selectComponent}
          />
        </div>
        {selected && (
          <section style={{ borderTop: '1px solid #334155', padding: '12px 0' }}>
            <DetailPanel component={selected} bom={dataset.bom} />
          </section>
        )}
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
    }}>
      {selected ? (
        <DetailPanel component={selected} bom={dataset.bom} />
      ) : (
        <DetailPlaceholder compact={false} />
      )}
    </div>
  );
}

function MobileToolbar({
  board, setBoard, sideFilter, setSideFilter,
}: {
  board: BoardId;
  setBoard: (b: BoardId) => void;
  sideFilter: SideFilter;
  setSideFilter: (s: SideFilter) => void;
}) {
  return (
    <div style={{
      display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap',
      paddingBottom: '8px', borderBottom: '1px solid #334155', marginBottom: '8px',
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
          No Parts List entry matches {component.bomRef}.
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
          <Field label="Unit cost" value={line.unitCostUsd !== undefined ? `$${line.unitCostUsd.toFixed(2)}` : '\u2014'} />

          <SourceLinks
            digikeyPn={line.digikeyPn}
            mouserPn={line.mouserPn}
            lcscPn={line.lcscPn}
            datasheetUrl={line.datasheetUrl}
          />
        </>
      )}
    </div>
  );
}

function SourceLinks({ digikeyPn, mouserPn, lcscPn, datasheetUrl }: {
  digikeyPn?: string | null;
  mouserPn?: string | null;
  lcscPn?: string | null;
  datasheetUrl?: string | null;
}) {
  const hasAny = digikeyPn || mouserPn || lcscPn || datasheetUrl;
  if (!hasAny) return null;

  const linkStyle: React.CSSProperties = { fontSize: '11px', color: '#60a5fa', textDecoration: 'none' };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: '6px',
      padding: '8px 10px', background: '#0f172a', border: '1px solid #1e293b',
      borderRadius: '5px',
    }}>
      <span style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Sources
      </span>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {digikeyPn && (
          <a href={`https://www.digikey.com/en/products/result?keywords=${encodeURIComponent(digikeyPn)}`}
            target="_blank" rel="noreferrer" title={digikeyPn} style={linkStyle}>Digi-Key</a>
        )}
        {mouserPn && (
          <a href={`https://www.mouser.com/ProductDetail/${encodeURIComponent(mouserPn)}`}
            target="_blank" rel="noreferrer" title={mouserPn} style={linkStyle}>Mouser</a>
        )}
        {lcscPn && (
          <a href={`https://www.lcsc.com/product-detail/${encodeURIComponent(lcscPn)}.html`}
            target="_blank" rel="noreferrer" title={lcscPn} style={linkStyle}>LCSC</a>
        )}
        {datasheetUrl && (
          <a href={datasheetUrl} target="_blank" rel="noreferrer" style={linkStyle}>Datasheet</a>
        )}
      </div>
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

function DetailPlaceholder({ compact }: { compact: boolean }) {
  return (
    <div style={{
      padding: compact ? '16px 8px' : '24px 8px', color: '#64748b', fontSize: '12px',
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
