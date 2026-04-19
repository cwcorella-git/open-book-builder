import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDataset } from '../lib/dataset-context';
import { useBreakpoint, type Breakpoint } from '../lib/use-breakpoint';
import type { BomLine, BoardId } from '../lib/types';
import { buildDigiKeyCsv, summarizeExport } from '../lib/digikey-csv';
import { saveTextFile } from '../lib/exporter';

const EXPORT_FILENAME = 'open-book-digikey-bom.csv';
const TOAST_MS = 3000;

type BoardFilter = 'all' | BoardId;

const BOARD_LABEL_FULL: Record<BoardId, string> = {
  'c1-main': 'Main Board (C1)',
  'c2-driver': 'E-Paper Driver (C2)',
};

const BOARD_LABEL_SHORT: Record<BoardId, string> = {
  'c1-main': 'C1',
  'c2-driver': 'C2',
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
  const bp = useBreakpoint();
  const compact = bp === 'compact';

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

  const { perUnitUsd } = dataset.costSummary;
  const asideWidth = bp === 'wide' ? '340px' : '260px';

  return (
    <div style={{
      display: 'flex',
      flexDirection: compact ? 'column' : 'row',
      gap: compact ? '12px' : '16px',
      height: '100%',
    }}>
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
          bp={bp}
        />
        <BomTable
          rows={rows}
          qtyMultiplier={qtyMultiplier}
          selectedKey={selectedKey}
          onSelect={setSelectedKey}
          bp={bp}
        />
        <Footer
          perUnitUsd={perUnitUsd}
          qtyMultiplier={qtyMultiplier}
          bp={bp}
        />
      </section>

      {compact ? (
        selected && (
          <section style={{
            borderTop: '1px solid #334155',
            paddingTop: '12px',
          }}>
            <DetailPanel line={selected} />
          </section>
        )
      ) : (
        <aside style={{
          width: asideWidth,
          flexShrink: 0,
          borderLeft: '1px solid #334155',
          paddingLeft: '16px',
          overflow: 'auto',
        }}>
          {selected ? <DetailPanel line={selected} /> : <DetailPlaceholder />}
        </aside>
      )}
    </div>
  );
}

function Toolbar({
  filter, setFilter, qtyMultiplier, setQtyMultiplier,
  includeOptional, setIncludeOptional, rowCount, bom, bp,
}: {
  filter: BoardFilter; setFilter: (f: BoardFilter) => void;
  qtyMultiplier: number; setQtyMultiplier: (n: number) => void;
  includeOptional: boolean; setIncludeOptional: (b: boolean) => void;
  rowCount: number;
  bom: BomLine[];
  bp: Breakpoint;
}) {
  const compact = bp === 'compact';
  const wide = bp === 'wide';

  function filterLabel(f: typeof FILTERS[number]): string {
    if (wide) return f.label;
    if (f.id === 'all') return 'All';
    if (f.id === 'c1-main') return compact ? 'C1' : 'Main';
    return compact ? 'C2' : 'Driver';
  }

  return (
    <div style={{
      display: 'flex', gap: compact ? '6px' : '16px', alignItems: 'center', flexWrap: 'wrap',
      paddingBottom: compact ? '8px' : '12px', borderBottom: '1px solid #334155', marginBottom: '8px',
    }}>
      <div style={{ display: 'flex', gap: '4px' }}>
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            style={{
              padding: compact ? '4px 8px' : '4px 10px', fontSize: compact ? '10px' : '11px',
              background: f.id === filter ? '#334155' : 'transparent',
              color: '#e2e8f0',
              border: '1px solid ' + (f.id === filter ? '#475569' : '#334155'),
              borderRadius: '4px', cursor: 'pointer',
            }}
          >
            {filterLabel(f)}
          </button>
        ))}
      </div>

      <label style={{ fontSize: compact ? '10px' : '11px', color: '#94a3b8', display: 'flex', gap: '4px', alignItems: 'center' }}>
        {wide ? 'Build qty' : 'Qty'}
        <input
          type="number" min={1} max={999} value={qtyMultiplier}
          onChange={(e) => {
            const parsed = parseInt(e.target.value, 10);
            setQtyMultiplier(Number.isFinite(parsed) && parsed > 0 ? parsed : 1);
          }}
          style={{
            width: compact ? '44px' : '56px', padding: '3px 6px', fontSize: compact ? '10px' : '11px',
            background: '#0f172a', color: '#e2e8f0',
            border: '1px solid #334155', borderRadius: '3px',
          }}
        />
      </label>

      <label style={{ fontSize: compact ? '10px' : '11px', color: '#94a3b8', display: 'flex', gap: '4px', alignItems: 'center' }}>
        <input
          type="checkbox" checked={includeOptional}
          onChange={(e) => setIncludeOptional(e.target.checked)}
          style={{ margin: 0 }}
        />
        {compact ? 'Opt' : wide ? 'Include optional lines' : 'Optional'}
      </label>

      <ExportSlot
        bom={bom}
        qtyMultiplier={qtyMultiplier}
        includeOptional={includeOptional}
        rowCount={rowCount}
        bp={bp}
      />
    </div>
  );
}

function ExportSlot({
  bom, qtyMultiplier, includeOptional, rowCount, bp,
}: {
  bom: BomLine[];
  qtyMultiplier: number;
  includeOptional: boolean;
  rowCount: number;
  bp: Breakpoint;
}) {
  const wide = bp === 'wide';
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
      {wide && (
        <>
          <span style={{ fontSize: '11px', color: '#64748b' }}>
            {rowCount} rows shown
          </span>
          <span style={{ fontSize: '11px', color: '#64748b' }}>
            · {includedCount} included · {skippedCount} skipped (no Digi-Key part number)
          </span>
        </>
      )}
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
  rows, qtyMultiplier, selectedKey, onSelect, bp,
}: {
  rows: BomLine[]; qtyMultiplier: number;
  selectedKey: string | null; onSelect: (key: string) => void;
  bp: Breakpoint;
}) {
  const headers = bp === 'compact'
    ? ['Refs', 'Description', 'Qty', 'Cost']
    : bp === 'medium'
    ? ['Board', 'Refs', 'Description', 'Qty', 'Cost']
    : ['Board', 'Refs', 'Description', 'Part Number', 'Qty', 'Qty × ' + qtyMultiplier,
       'Unit Cost', 'Line Total', ''];

  const colCount = headers.length;

  return (
    <div style={{ flex: 1, overflow: 'auto', border: '1px solid #1e293b', borderRadius: '6px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', color: '#e2e8f0' }}>
        <thead style={{ position: 'sticky', top: 0, background: '#0f172a', zIndex: 1 }}>
          <tr>
            {headers.map((h, i) => (
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
            return (
              <BomRow
                key={key}
                line={line}
                isSelected={isSelected}
                totalQty={totalQty}
                lineUnit={lineUnit}
                lineTotal={lineTotal}
                onSelect={() => onSelect(key)}
                bp={bp}
              />
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={colCount} style={{ ...tdStyle, textAlign: 'center', color: '#64748b', padding: '24px' }}>
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
  line, isSelected, totalQty, lineUnit, lineTotal, onSelect, bp,
}: {
  line: BomLine;
  isSelected: boolean; totalQty: number;
  lineUnit: number | null | undefined; lineTotal: number | null;
  onSelect: () => void;
  bp: Breakpoint;
}) {
  return (
    <tr
      onClick={onSelect}
      style={{
        cursor: 'pointer',
        background: isSelected ? '#1e293b' : 'transparent',
        borderBottom: '1px solid #1e293b',
        opacity: line.optional ? 0.75 : 1,
      }}
    >
      {bp === 'compact' ? (
        <>
          <td style={tdStyle}>
            <span style={{ fontFamily: 'monospace', color: '#cbd5e1', fontSize: '10px' }}>
              {line.refs.join(', ') || '—'}
            </span>
          </td>
          <td style={{ ...tdStyle, maxWidth: '140px' }}>
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '10px' }}>
              {line.description}
            </div>
          </td>
          <td style={{ ...tdStyle, textAlign: 'right', fontSize: '10px' }}>{totalQty}</td>
          <td style={{ ...tdStyle, textAlign: 'right', fontSize: '10px' }}>{formatUsd(lineUnit)}</td>
        </>
      ) : bp === 'medium' ? (
        <>
          <td style={tdStyle}>
            <BoardPill board={line.board} short />
          </td>
          <td style={tdStyle}>
            <span style={{ fontFamily: 'monospace', color: '#cbd5e1' }}>
              {line.refs.join(', ') || '—'}
            </span>
          </td>
          <td style={{ ...tdStyle, maxWidth: '200px' }}>
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {line.description}
            </div>
          </td>
          <td style={{ ...tdStyle, textAlign: 'right' }}>{totalQty}</td>
          <td style={{ ...tdStyle, textAlign: 'right' }}>{formatUsd(lineUnit)}</td>
        </>
      ) : (
        <>
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
            {line.mpn}
          </td>
          <td style={{ ...tdStyle, textAlign: 'right' }}>{line.qty}</td>
          <td style={{ ...tdStyle, textAlign: 'right', color: '#94a3b8' }}>{totalQty}</td>
          <td style={{ ...tdStyle, textAlign: 'right' }}>{formatUsd(lineUnit)}</td>
          <td style={{ ...tdStyle, textAlign: 'right' }}>{formatUsd(lineTotal)}</td>
          <td style={tdStyle}>
            {line.optional && <OptionalChip />}
          </td>
        </>
      )}
    </tr>
  );
}

function Footer({
  perUnitUsd, qtyMultiplier, bp,
}: {
  perUnitUsd: number;
  qtyMultiplier: number;
  bp: Breakpoint;
}) {
  const compact = bp === 'compact';
  const projected = perUnitUsd * qtyMultiplier;
  return (
    <div style={{
      marginTop: '8px', padding: compact ? '8px 10px' : '10px 12px', borderTop: '1px solid #334155',
      fontSize: '11px', color: '#cbd5e1',
      display: 'flex', gap: compact ? '12px' : '24px', flexWrap: 'wrap', alignItems: 'baseline',
    }}>
      <span><b style={{ color: '#f1f5f9' }}>Per unit:</b> ${perUnitUsd.toFixed(2)}</span>
      {qtyMultiplier > 1 && (
        <span><b style={{ color: '#f1f5f9' }}>× {qtyMultiplier}:</b> ${projected.toFixed(2)}</span>
      )}
      {bp === 'wide' && (
        <span style={{ marginLeft: 'auto', color: '#64748b', fontStyle: 'italic' }}>
          E-Paper Driver internals excluded — they arrive pre-assembled as a single unit from the fab house.
        </span>
      )}
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

      <SourceLinks
        digikeyPn={line.digikeyPn}
        mouserPn={line.mouserPn}
        lcscPn={line.lcscPn}
        datasheetUrl={line.datasheetUrl}
      />

      <div style={{
        marginTop: '4px', padding: '8px', fontSize: '11px',
        background: '#0f172a', border: '1px solid #1e293b', borderRadius: '4px',
        color: '#64748b',
      }}>
        Raw CSV description: <span style={{ color: '#94a3b8' }}>{line.description}</span>
      </div>
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
          <DistributorLink
            name="Digi-Key"
            pn={digikeyPn}
            href={`https://www.digikey.com/en/products/result?keywords=${encodeURIComponent(digikeyPn)}`}
          />
        )}
        {mouserPn && (
          <DistributorLink
            name="Mouser"
            pn={mouserPn}
            href={`https://www.mouser.com/ProductDetail/${encodeURIComponent(mouserPn)}`}
          />
        )}
        {lcscPn && (
          <DistributorLink
            name="LCSC"
            pn={lcscPn}
            href={`https://www.lcsc.com/product-detail/${encodeURIComponent(lcscPn)}.html`}
          />
        )}
        {datasheetUrl && (
          <a
            href={datasheetUrl}
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: '11px', color: '#60a5fa', textDecoration: 'none' }}
          >
            Datasheet
          </a>
        )}
      </div>
    </div>
  );
}

function DistributorLink({ name, pn, href }: { name: string; pn: string; href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      title={pn}
      style={{ fontSize: '11px', color: '#60a5fa', textDecoration: 'none' }}
    >
      {name}
    </a>
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
      Click a Parts List row to see the part's function, datasheet, and distributor
      part numbers.
    </div>
  );
}

function BoardPill({ board, short = false }: { board: BoardId; short?: boolean }) {
  return (
    <span style={{
      padding: '2px 6px', fontSize: '10px',
      background: board === 'c1-main' ? '#1e40af' : '#7c3aed',
      color: '#e0e7ff',
      borderRadius: '3px',
      letterSpacing: '0.3px',
      whiteSpace: 'nowrap',
    }}>
      {short ? BOARD_LABEL_SHORT[board] : BOARD_LABEL_FULL[board]}
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
