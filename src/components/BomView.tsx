import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDataset } from '../lib/dataset-context';
import type { BomLine, BomComparison, BoardId } from '../lib/types';
import { buildDigiKeyCsv, summarizeExport } from '../lib/digikey-csv';
import { saveTextFile } from '../lib/exporter';

const EXPORT_FILENAME = 'open-book-digikey-bom.csv';
const TOAST_MS = 3000;

type BoardFilter = 'all' | BoardId;

const BOARD_LABEL: Record<BoardId, string> = {
  'c1-main': 'Main Board (C1)',
  'c2-driver': 'E-Paper Driver (C2)',
};

const FILTERS: { id: BoardFilter; label: string }[] = [
  { id: 'all', label: 'Both Boards' },
  { id: 'c1-main', label: 'Main Board' },
  { id: 'c2-driver', label: 'E-Paper Driver' },
];

function lineKey(line: BomLine): string {
  return `${line.board}:${line.mpn}:${line.refs.join(',')}`;
}

function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `$${value.toFixed(2)}`;
}

export function BomView() {
  const dataset = useDataset();
  const [filter, setFilter] = useState<BoardFilter>('all');
  const [qtyMultiplier, setQtyMultiplier] = useState<number>(1);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [includeOptional, setIncludeOptional] = useState<boolean>(true);

  const rows = useMemo(() => {
    return dataset.bom.filter((line) => {
      if (filter !== 'all' && line.board !== filter) return false;
      if (!includeOptional && line.optional) return false;
      return true;
    });
  }, [dataset.bom, filter, includeOptional]);

  const selected = useMemo(
    () => (selectedKey ? rows.find((r) => lineKey(r) === selectedKey) ?? null : null),
    [rows, selectedKey],
  );

  const { perUnitUsd, perTenUnitsUsd, missingLineItems } = dataset.costSummary;

  return (
    <div style={{ display: 'flex', gap: '16px', height: '100%' }}>
      <section style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Toolbar
          filter={filter}
          setFilter={setFilter}
          qtyMultiplier={qtyMultiplier}
          setQtyMultiplier={setQtyMultiplier}
          includeOptional={includeOptional}
          setIncludeOptional={setIncludeOptional}
          rowCount={rows.length}
          bom={dataset.bom}
        />
        <BomTable
          rows={rows}
          qtyMultiplier={qtyMultiplier}
          selectedKey={selectedKey}
          onSelect={setSelectedKey}
          bomComparison={dataset.bomComparison}
        />
        <Footer
          perUnitUsd={perUnitUsd}
          perTenUnitsUsd={perTenUnitsUsd}
          qtyMultiplier={qtyMultiplier}
          missingLineItems={missingLineItems}
        />
      </section>

      <aside style={{
        width: '340px',
        flexShrink: 0,
        borderLeft: '1px solid #334155',
        paddingLeft: '16px',
        overflow: 'auto',
      }}>
        {selected ? <DetailPanel line={selected} /> : <DetailPlaceholder />}
      </aside>
    </div>
  );
}

function Toolbar({
  filter, setFilter, qtyMultiplier, setQtyMultiplier,
  includeOptional, setIncludeOptional, rowCount, bom,
}: {
  filter: BoardFilter; setFilter: (f: BoardFilter) => void;
  qtyMultiplier: number; setQtyMultiplier: (n: number) => void;
  includeOptional: boolean; setIncludeOptional: (b: boolean) => void;
  rowCount: number;
  bom: BomLine[];
}) {
  return (
    <div style={{
      display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap',
      paddingBottom: '12px', borderBottom: '1px solid #334155', marginBottom: '8px',
    }}>
      <div style={{ display: 'flex', gap: '4px' }}>
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            style={{
              padding: '4px 10px', fontSize: '11px',
              background: f.id === filter ? '#334155' : 'transparent',
              color: '#e2e8f0',
              border: '1px solid ' + (f.id === filter ? '#475569' : '#334155'),
              borderRadius: '4px', cursor: 'pointer',
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <label style={{ fontSize: '11px', color: '#94a3b8', display: 'flex', gap: '6px', alignItems: 'center' }}>
        Build qty
        <input
          type="number" min={1} max={999} value={qtyMultiplier}
          onChange={(e) => {
            const parsed = parseInt(e.target.value, 10);
            setQtyMultiplier(Number.isFinite(parsed) && parsed > 0 ? parsed : 1);
          }}
          style={{
            width: '56px', padding: '3px 6px', fontSize: '11px',
            background: '#0f172a', color: '#e2e8f0',
            border: '1px solid #334155', borderRadius: '3px',
          }}
        />
      </label>

      <label style={{ fontSize: '11px', color: '#94a3b8', display: 'flex', gap: '6px', alignItems: 'center' }}>
        <input
          type="checkbox" checked={includeOptional}
          onChange={(e) => setIncludeOptional(e.target.checked)}
        />
        Include optional lines
      </label>

      <ExportSlot
        bom={bom}
        qtyMultiplier={qtyMultiplier}
        includeOptional={includeOptional}
        rowCount={rowCount}
      />
    </div>
  );
}

function ExportSlot({
  bom, qtyMultiplier, includeOptional, rowCount,
}: {
  bom: BomLine[];
  qtyMultiplier: number;
  includeOptional: boolean;
  rowCount: number;
}) {
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  // Cancel any pending toast-clear on unmount.
  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const { includedCount, skippedCount } = useMemo(
    () => summarizeExport(bom, includeOptional),
    [bom, includeOptional],
  );

  const disabled = busy || includedCount === 0;

  const handleExport = useCallback(async () => {
    setBusy(true);
    try {
      const result = buildDigiKeyCsv(bom, { qtyMultiplier, includeOptional });
      const outcome = await saveTextFile(EXPORT_FILENAME, result.csv);
      if (outcome === 'saved') {
        const noun = result.includedCount === 1 ? 'line' : 'lines';
        setToast(`Saved ${result.includedCount} ${noun} to ${EXPORT_FILENAME}`);
        if (timeoutRef.current !== null) {
          window.clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = window.setTimeout(() => setToast(null), TOAST_MS);
      }
    } catch (err) {
      console.error('Digi-Key CSV export failed:', err);
      setToast(`Export failed: ${err instanceof Error ? err.message : String(err)}`);
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = window.setTimeout(() => setToast(null), TOAST_MS);
    } finally {
      setBusy(false);
    }
  }, [bom, qtyMultiplier, includeOptional]);

  const isError = toast?.startsWith('Export failed');

  return (
    <div style={{
      marginLeft: 'auto', display: 'flex', gap: '10px',
      alignItems: 'center', flexWrap: 'wrap',
    }}>
      <span style={{ fontSize: '11px', color: '#64748b' }}>
        {rowCount} rows shown
      </span>
      <span style={{ fontSize: '11px', color: '#64748b' }}>
        · {includedCount} included · {skippedCount} skipped (no Digi-Key part number)
      </span>
      {toast && (
        <span style={{
          fontSize: '11px',
          color: isError ? '#fca5a5' : '#86efac',
        }}>
          {toast}
        </span>
      )}
      <button
        onClick={handleExport}
        disabled={disabled}
        title={
          includedCount === 0
            ? 'No exportable lines'
            : `Export ${includedCount} lines to ${EXPORT_FILENAME}`
        }
        style={{
          padding: '5px 12px', fontSize: '11px',
          background: disabled ? '#1e293b' : '#1d4ed8',
          color: disabled ? '#64748b' : '#f1f5f9',
          border: '1px solid ' + (disabled ? '#334155' : '#2563eb'),
          borderRadius: '4px',
          cursor: disabled ? 'not-allowed' : 'pointer',
          fontWeight: 500,
        }}
      >
        {busy ? 'Exporting…' : 'Export Digi-Key CSV'}
      </button>
    </div>
  );
}

function BomTable({
  rows, qtyMultiplier, selectedKey, onSelect, bomComparison,
}: {
  rows: BomLine[]; qtyMultiplier: number;
  selectedKey: string | null; onSelect: (key: string) => void;
  bomComparison: BomComparison[];
}) {
  const [expandedMpn, setExpandedMpn] = useState<string | null>(null);

  const comparisonByRef = useMemo(() => {
    const map = new Map<string, BomComparison>();
    for (const c of bomComparison) map.set(c.bomRef, c);
    return map;
  }, [bomComparison]);

  return (
    <div style={{ flex: 1, overflow: 'auto', border: '1px solid #1e293b', borderRadius: '6px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', color: '#e2e8f0' }}>
        <thead style={{ position: 'sticky', top: 0, background: '#0f172a', zIndex: 1 }}>
          <tr>
            {['Board', 'Refs', 'Description', 'Part Number', 'Qty', 'Qty × ' + qtyMultiplier,
              'Unit Cost', 'Line Total', ''].map((h, i) => (
              <th key={i} style={thStyle}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((line) => {
            const key = lineKey(line);
            const isSelected = key === selectedKey;
            const totalQty = line.qty * qtyMultiplier;
            const lineUnit = line.unitCostUsd;
            const lineTotal = lineUnit !== undefined && lineUnit !== null
              ? lineUnit * totalQty
              : null;
            const comparison = comparisonByRef.get(line.mpn);
            const isExpanded = expandedMpn === line.mpn;
            return (
              <BomRow
                key={key}
                line={line}
                isSelected={isSelected}
                totalQty={totalQty}
                lineUnit={lineUnit}
                lineTotal={lineTotal}
                comparison={comparison}
                isExpanded={isExpanded}
                onSelect={() => onSelect(key)}
                onToggleExpand={() => setExpandedMpn(isExpanded ? null : line.mpn)}
              />
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={9} style={{ ...tdStyle, textAlign: 'center', color: '#64748b', padding: '24px' }}>
                No rows match the current filter.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function BomRow({
  line, isSelected, totalQty, lineUnit, lineTotal,
  comparison, isExpanded, onSelect, onToggleExpand,
}: {
  line: BomLine;
  isSelected: boolean; totalQty: number;
  lineUnit: number | null | undefined; lineTotal: number | null;
  comparison: BomComparison | undefined;
  isExpanded: boolean;
  onSelect: () => void;
  onToggleExpand: () => void;
}) {
  const hasComparison = comparison !== undefined;
  const hasConflict = comparison?.conflict === true;

  return (
    <>
      <tr
        onClick={() => { onSelect(); onToggleExpand(); }}
        style={{
          cursor: 'pointer',
          background: isSelected ? '#1e293b' : 'transparent',
          borderBottom: isExpanded ? 'none' : '1px solid #1e293b',
          opacity: line.optional ? 0.75 : 1,
        }}
      >
        <td style={tdStyle}>
          <BoardPill board={line.board} />
        </td>
        <td style={tdStyle}>
          <span style={{ fontFamily: 'monospace', color: '#cbd5e1' }}>
            {line.refs.join(', ') || '—'}
          </span>
        </td>
        <td style={{ ...tdStyle, maxWidth: '260px' }}>
          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {line.description}
          </div>
        </td>
        <td style={{ ...tdStyle, fontFamily: 'monospace', color: '#94a3b8' }}>
          <span style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
            {line.mpn}
            {hasConflict && <ConflictBadge />}
          </span>
        </td>
        <td style={{ ...tdStyle, textAlign: 'right' }}>{line.qty}</td>
        <td style={{ ...tdStyle, textAlign: 'right', color: '#94a3b8' }}>{totalQty}</td>
        <td style={{ ...tdStyle, textAlign: 'right' }}>{formatUsd(lineUnit)}</td>
        <td style={{ ...tdStyle, textAlign: 'right' }}>{formatUsd(lineTotal)}</td>
        <td style={tdStyle}>
          {line.optional && <OptionalChip />}
        </td>
      </tr>
      {isExpanded && hasComparison && (
        <tr style={{ background: '#0f172a', borderBottom: '1px solid #1e293b' }}>
          <td colSpan={9} style={{ padding: '0 10px 10px' }}>
            <ComparisonCard comparison={comparison} />
          </td>
        </tr>
      )}
    </>
  );
}

const COMPARISON_SOURCES = ['Canonical', 'COGS-LIST', 'PDF', 'April 2025'] as const;

function ComparisonCard({ comparison }: { comparison: BomComparison }) {
  const sources: { label: string; qty: number | undefined; cost: number | undefined }[] = [
    { label: 'Canonical', qty: comparison.canonicalQty, cost: comparison.canonicalCost },
    { label: 'COGS-LIST', qty: comparison.cogsQty, cost: comparison.cogsCost },
    { label: 'PDF', qty: comparison.pdfQty, cost: comparison.pdfCost },
    { label: 'April 2025', qty: comparison.april2025Qty, cost: comparison.april2025Cost },
  ];

  const canonicalCost = comparison.canonicalCost;

  return (
    <div style={{
      marginTop: '6px', padding: '10px 12px',
      background: '#1e293b', border: '1px solid #334155',
      borderRadius: '6px', fontSize: '11px',
    }}>
      <div style={{
        display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px',
      }}>
        <span style={{
          fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px',
          color: '#64748b', fontWeight: 600,
        }}>
          Source comparison
        </span>
        {comparison.conflict && <ConflictBadge />}
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', color: '#e2e8f0' }}>
        <thead>
          <tr>
            <th style={compTh} />
            {COMPARISON_SOURCES.map((s) => (
              <th key={s} style={{ ...compTh, textAlign: 'right' }}>{s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={compTd}>Qty</td>
            {sources.map((s) => (
              <td key={s.label} style={{ ...compTd, textAlign: 'right' }}>
                {s.qty !== undefined && s.qty !== null ? s.qty : '—'}
              </td>
            ))}
          </tr>
          <tr>
            <td style={compTd}>Unit $</td>
            {sources.map((s) => {
              const isDiff = canonicalCost !== undefined && canonicalCost !== null
                && s.cost !== undefined && s.cost !== null
                && Math.abs(s.cost - canonicalCost) > 0.01;
              return (
                <td key={s.label} style={{
                  ...compTd, textAlign: 'right',
                  color: isDiff ? '#fbbf24' : '#e2e8f0',
                }}>
                  {formatUsd(s.cost)}
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>

      {comparison.note && (
        <div style={{
          marginTop: '8px', padding: '6px 10px',
          background: '#0f172a', borderRadius: '3px',
          borderLeft: comparison.conflict ? '3px solid #fbbf24' : '3px solid #334155',
          color: '#94a3b8', fontSize: '11px', lineHeight: 1.4,
        }}>
          {comparison.note}
        </div>
      )}
    </div>
  );
}

function ConflictBadge() {
  return (
    <span style={{
      padding: '1px 5px', fontSize: '9px',
      background: '#78350f', color: '#fbbf24',
      borderRadius: '3px', letterSpacing: '0.3px',
      textTransform: 'uppercase', fontWeight: 600,
    }}>
      diff
    </span>
  );
}

const compTh: React.CSSProperties = {
  padding: '4px 8px', fontSize: '10px', fontWeight: 600,
  color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.4px',
  borderBottom: '1px solid #334155',
};

const compTd: React.CSSProperties = {
  padding: '4px 8px', fontSize: '11px',
  borderBottom: '1px solid #1e293b',
};

function Footer({
  perUnitUsd, perTenUnitsUsd, qtyMultiplier, missingLineItems,
}: {
  perUnitUsd: number; perTenUnitsUsd: number;
  qtyMultiplier: number; missingLineItems: string[];
}) {
  const projected = perUnitUsd * qtyMultiplier;
  return (
    <div style={{
      marginTop: '8px', padding: '10px 12px', borderTop: '1px solid #334155',
      fontSize: '11px', color: '#cbd5e1',
      display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'baseline',
    }}>
      <span><b style={{ color: '#f1f5f9' }}>Per unit:</b> ${perUnitUsd.toFixed(2)}</span>
      <span><b style={{ color: '#f1f5f9' }}>Per 10:</b> ${perTenUnitsUsd.toFixed(2)}</span>
      {qtyMultiplier !== 1 && qtyMultiplier !== 10 && (
        <span><b style={{ color: '#f1f5f9' }}>× {qtyMultiplier}:</b> ${projected.toFixed(2)}</span>
      )}
      {missingLineItems.length > 0 && (
        <span style={{ color: '#fbbf24' }}>
          ⚠ {missingLineItems.length} line{missingLineItems.length === 1 ? '' : 's'} without price:
          {' '}
          <span style={{ fontFamily: 'monospace' }}>{missingLineItems.join(', ')}</span>
        </span>
      )}
      <span style={{ marginLeft: 'auto', color: '#64748b', fontStyle: 'italic' }}>
        E-Paper Driver internals excluded — they arrive pre-assembled as a single unit from the fab house.
      </span>
    </div>
  );
}

function DetailPanel({ line }: { line: BomLine }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '12px', color: '#e2e8f0' }}>
      <header style={{ display: 'flex', gap: '8px', alignItems: 'baseline', flexWrap: 'wrap' }}>
        <h2 style={{ fontSize: '14px', color: '#f1f5f9', margin: 0 }}>
          {line.refs.join(', ') || '(no ref)'}
        </h2>
        <BoardPill board={line.board} />
        {line.optional && <OptionalChip />}
      </header>

      <div style={{ color: '#cbd5e1', lineHeight: 1.45 }}>
        {line.function}
      </div>

      <Field label="Part Number" value={<span style={{ fontFamily: 'monospace' }}>{line.mpn}</span>} />
      {line.manufacturer && <Field label="Manufacturer" value={line.manufacturer} />}
      {line.footprint && <Field label="Footprint" value={line.footprint} />}
      <Field label="Qty per unit" value={String(line.qty)} />
      <Field label="Unit cost" value={formatUsd(line.unitCostUsd)} />
      {line.digikeyPn && (
        <Field label="Digi-Key" value={<span style={{ fontFamily: 'monospace' }}>{line.digikeyPn}</span>} />
      )}
      {line.mouserPn && (
        <Field label="Mouser" value={<span style={{ fontFamily: 'monospace' }}>{line.mouserPn}</span>} />
      )}
      {line.datasheetUrl && (
        <Field
          label="Datasheet"
          value={
            <a href={line.datasheetUrl} target="_blank" rel="noreferrer"
               style={{ color: '#60a5fa', textDecoration: 'none' }}>
              View Datasheet
            </a>
          }
        />
      )}

      <div style={{
        marginTop: '4px', padding: '8px', fontSize: '11px',
        background: '#0f172a', border: '1px solid #1e293b', borderRadius: '4px',
        color: '#64748b',
      }}>
        Raw BOM description: <span style={{ color: '#94a3b8' }}>{line.description}</span>
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

function DetailPlaceholder() {
  return (
    <div style={{
      padding: '24px 8px', color: '#64748b', fontSize: '12px',
      fontStyle: 'italic', lineHeight: 1.5,
    }}>
      Click a BOM row to see the part's function, datasheet, and distributor
      part numbers.
    </div>
  );
}

function BoardPill({ board }: { board: BoardId }) {
  return (
    <span style={{
      padding: '2px 6px', fontSize: '10px',
      background: board === 'c1-main' ? '#1e40af' : '#7c3aed',
      color: '#e0e7ff',
      borderRadius: '3px',
      letterSpacing: '0.3px',
    }}>
      {BOARD_LABEL[board]}
    </span>
  );
}

function OptionalChip() {
  return (
    <span style={{
      padding: '2px 6px', fontSize: '10px',
      background: '#78350f', color: '#fde68a',
      borderRadius: '3px', letterSpacing: '0.3px',
    }}>
      OPTIONAL
    </span>
  );
}

const thStyle: React.CSSProperties = {
  padding: '8px 10px',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '10px',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  color: '#64748b',
  borderBottom: '1px solid #334155',
};

const tdStyle: React.CSSProperties = {
  padding: '6px 10px',
  verticalAlign: 'top',
};
