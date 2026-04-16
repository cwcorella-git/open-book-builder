import { useMemo, useState } from 'react';
import { useDataset } from '../lib/dataset-context';
import { useNavigation } from '../lib/navigation-context';
import type { Discrepancy, Severity } from '../lib/types';
import { useDiscrepancyResolution } from '../lib/use-discrepancy-resolution';

type SeverityFilter = 'all' | Severity;

const SEVERITY_COLOR: Record<Severity, string> = {
  'build-critical': '#ef4444',
  'cost-impact': '#f97316',
  naming: '#fbbf24',
  informational: '#64748b',
};

const SEVERITY_LABEL: Record<Severity, string> = {
  'build-critical': 'Build-critical',
  'cost-impact': 'Cost impact',
  naming: 'Naming',
  informational: 'Informational',
};

const SEVERITY_ORDER: Severity[] = [
  'build-critical',
  'cost-impact',
  'naming',
  'informational',
];

const FILTERS: { id: SeverityFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  ...SEVERITY_ORDER.map((s) => ({ id: s as SeverityFilter, label: SEVERITY_LABEL[s] })),
];

export function DiscrepancyView() {
  const { discrepancies } = useDataset();
  const { isResolved, setResolved } = useDiscrepancyResolution(discrepancies);

  const [filter, setFilter] = useState<SeverityFilter>('all');
  const [hideResolved, setHideResolved] = useState(false);

  const grouped = useMemo(() => {
    const map: Record<Severity, Discrepancy[]> = {
      'build-critical': [],
      'cost-impact': [],
      naming: [],
      informational: [],
    };
    for (const d of discrepancies) {
      if (filter !== 'all' && d.severity !== filter) continue;
      if (hideResolved && isResolved(d.id)) continue;
      map[d.severity].push(d);
    }
    return map;
  }, [discrepancies, filter, hideResolved, isResolved]);

  const visibleCount = SEVERITY_ORDER.reduce(
    (n, s) => n + grouped[s].length,
    0,
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '12px' }}>
      <Toolbar
        filter={filter}
        setFilter={setFilter}
        hideResolved={hideResolved}
        setHideResolved={setHideResolved}
        visibleCount={visibleCount}
        totalCount={discrepancies.length}
      />

      <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {SEVERITY_ORDER.map((severity) => {
          const items = grouped[severity];
          if (items.length === 0) return null;
          return (
            <section key={severity} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <SectionHeader severity={severity} count={items.length} />
              {items.map((d) => (
                <DiscrepancyCard
                  key={d.id}
                  discrepancy={d}
                  resolved={isResolved(d.id)}
                  onToggle={(v) => setResolved(d.id, v)}
                />
              ))}
            </section>
          );
        })}

        {visibleCount === 0 && (
          <div style={{
            padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '13px',
            border: '1px dashed #334155', borderRadius: '8px',
          }}>
            No discrepancies match the current filter.
          </div>
        )}
      </div>
    </div>
  );
}

function Toolbar({
  filter, setFilter, hideResolved, setHideResolved, visibleCount, totalCount,
}: {
  filter: SeverityFilter; setFilter: (f: SeverityFilter) => void;
  hideResolved: boolean; setHideResolved: (b: boolean) => void;
  visibleCount: number; totalCount: number;
}) {
  return (
    <div style={{
      display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap',
      paddingBottom: '12px', borderBottom: '1px solid #334155',
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
        <input
          type="checkbox" checked={hideResolved}
          onChange={(e) => setHideResolved(e.target.checked)}
        />
        Hide resolved
      </label>

      <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#64748b' }}>
        {visibleCount} of {totalCount} shown
      </span>
    </div>
  );
}

function SectionHeader({ severity, count }: { severity: Severity; count: number }) {
  return (
    <h2 style={{
      display: 'flex', alignItems: 'baseline', gap: '10px',
      margin: 0, padding: '0 2px',
      fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.6px',
      color: '#cbd5e1',
    }}>
      <span style={{
        width: '8px', height: '8px', borderRadius: '50%',
        background: SEVERITY_COLOR[severity],
        display: 'inline-block',
      }} />
      {SEVERITY_LABEL[severity]}
      <span style={{ color: '#64748b', fontWeight: 400 }}>({count})</span>
    </h2>
  );
}

function DiscrepancyCard({
  discrepancy, resolved, onToggle,
}: {
  discrepancy: Discrepancy;
  resolved: boolean;
  onToggle: (value: boolean) => void;
}) {
  const accent = SEVERITY_COLOR[discrepancy.severity];
  return (
    <article style={{
      background: '#1e293b',
      border: '1px solid #334155',
      borderLeft: `4px solid ${accent}`,
      borderRadius: '6px',
      padding: '14px 16px',
      opacity: resolved ? 0.55 : 1,
      transition: 'opacity 150ms',
      display: 'flex', flexDirection: 'column', gap: '10px',
    }}>
      <header style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <SeverityPill severity={discrepancy.severity} />
            <span style={{ fontFamily: 'monospace', fontSize: '10px', color: '#64748b' }}>
              {discrepancy.id}
            </span>
          </div>
          <h3 style={{
            margin: 0, fontSize: '13px', color: '#f1f5f9',
            textDecoration: resolved ? 'line-through' : 'none',
          }}>
            {discrepancy.title}
          </h3>
        </div>

        <label style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          fontSize: '11px', color: resolved ? '#86efac' : '#94a3b8',
          cursor: 'pointer', userSelect: 'none', flexShrink: 0,
        }}>
          <input
            type="checkbox"
            checked={resolved}
            onChange={(e) => onToggle(e.target.checked)}
          />
          Resolved
        </label>
      </header>

      <p style={{
        margin: 0, fontSize: '12px', lineHeight: 1.5, color: '#cbd5e1',
      }}>
        {discrepancy.description}
      </p>

      {discrepancy.sources.length > 0 && (
        <ChipRow label="Sources" items={discrepancy.sources} tone="neutral" />
      )}

      {discrepancy.affectsComponents.length > 0 && (
        <ChipRow label="Affects" items={discrepancy.affectsComponents} tone="ref" />
      )}

      <blockquote style={{
        margin: 0, padding: '10px 12px',
        background: '#0f172a', borderLeft: `2px solid ${accent}`,
        borderRadius: '3px',
        fontSize: '12px', color: '#e2e8f0', lineHeight: 1.5,
      }}>
        <span style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Resolution:{' '}
        </span>
        {discrepancy.resolution}
      </blockquote>
    </article>
  );
}

function ChipRow({
  label, items, tone,
}: {
  label: string;
  items: string[];
  tone: 'neutral' | 'ref';
}) {
  // `tone === 'ref'` chips jump to the Board tab with that ref selected. Tone
  // `neutral` (Sources) stays as inert spans.
  const { navigateToComponent } = useNavigation();
  const chipBg = tone === 'ref' ? '#1e40af' : '#334155';
  const chipFg = tone === 'ref' ? '#e0e7ff' : '#cbd5e1';
  const chipStyle: React.CSSProperties = {
    padding: '2px 8px',
    background: chipBg,
    color: chipFg,
    borderRadius: '3px',
    fontSize: '10px',
    fontFamily: tone === 'ref' ? 'monospace' : 'inherit',
    wordBreak: 'break-all',
  };
  return (
    <div style={{ display: 'flex', gap: '6px', alignItems: 'baseline', flexWrap: 'wrap' }}>
      <span style={{
        fontSize: '10px', color: '#64748b',
        textTransform: 'uppercase', letterSpacing: '0.5px',
        minWidth: '60px',
      }}>
        {label}
      </span>
      {items.map((item) =>
        tone === 'ref' ? (
          <button
            key={item}
            type="button"
            onClick={() => navigateToComponent(item)}
            style={{ ...chipStyle, border: 'none', cursor: 'pointer', lineHeight: 1.2 }}
            title={`Jump to ${item} on the Board tab`}
          >
            {item}
          </button>
        ) : (
          <span key={item} style={chipStyle}>
            {item}
          </span>
        ),
      )}
    </div>
  );
}

function SeverityPill({ severity }: { severity: Severity }) {
  return (
    <span style={{
      padding: '2px 6px',
      fontSize: '10px',
      background: SEVERITY_COLOR[severity],
      color: severity === 'naming' ? '#1e293b' : '#fef2f2',
      borderRadius: '3px',
      letterSpacing: '0.3px',
      textTransform: 'uppercase',
      fontWeight: 600,
    }}>
      {SEVERITY_LABEL[severity]}
    </span>
  );
}
