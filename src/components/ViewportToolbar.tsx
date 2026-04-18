// Toolbar for the persistent viewport column. Board selector, side filter,
// color-by mode, traces toggle, and component/hole counts — extracted from
// the old BoardView toolbar so it can live above the shared BoardViewport.

import { useDataset } from '../lib/dataset-context';
import { useNavigation } from '../lib/navigation-context';
import { useViewport } from '../lib/viewport-context';
import { useBreakpoint } from '../lib/use-breakpoint';
import type { BoardId } from '../lib/types';
import type { ColorMode, SideFilter } from '../lib/scene-renderer';

const BOARDS: { id: BoardId; label: string }[] = [
  { id: 'c1-main', label: 'Main Board' },
  { id: 'c2-driver', label: 'E-Paper Driver' },
];

const SIDE_FILTERS: { id: SideFilter; label: string }[] = [
  { id: 'both', label: 'Both sides' },
  { id: 'top', label: 'Top' },
  { id: 'bottom', label: 'Bottom' },
];

const COLOR_MODES: { id: ColorMode; label: string }[] = [
  { id: 'side', label: 'Board Side' },
  { id: 'netCategory', label: 'Signal Type' },
];

export function ViewportToolbar() {
  const { board, setBoard, tab } = useNavigation();
  const { config, setConfig } = useViewport();
  const dataset = useDataset();
  const bp = useBreakpoint();
  const compact = bp === 'compact';
  const wide = bp === 'wide';

  const boardData = dataset.boards[board];

  function boardLabel(id: BoardId): string {
    if (wide) return id === 'c1-main' ? 'Main Board' : 'E-Paper Driver';
    return id === 'c1-main' ? 'Main' : 'Driver';
  }

  // Assembly is always c1-main; disable board switching on that tab.
  const boardSelectorDisabled = tab === 'assembly';

  return (
    <div style={{
      display: 'flex', gap: compact ? '6px' : wide ? '16px' : '10px', alignItems: 'center', flexWrap: 'wrap',
      paddingBottom: compact ? '8px' : '12px', borderBottom: '1px solid #334155', marginBottom: '8px',
    }}>
      <div style={{ display: 'flex', gap: '4px' }}>
        {BOARDS.map((b) => (
          <button
            key={b.id}
            onClick={() => !boardSelectorDisabled && setBoard(b.id)}
            disabled={boardSelectorDisabled}
            style={{
              ...pillStyle(b.id === board),
              ...(boardSelectorDisabled ? { opacity: 0.5, cursor: 'not-allowed' } : {}),
            }}
          >
            {boardLabel(b.id)}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '4px' }}>
        {SIDE_FILTERS.map((s) => (
          <button
            key={s.id}
            onClick={() => setConfig({ sideFilter: s.id })}
            style={pillStyle(s.id === config.sideFilter)}
          >
            {compact && s.id === 'both' ? 'All' : s.label}
          </button>
        ))}
      </div>

      {!compact && (
        <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
          {wide && <span style={{ fontSize: '10px', color: '#64748b', marginRight: '2px' }}>Color by:</span>}
          {COLOR_MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => setConfig({ colorMode: m.id })}
              style={pillStyle(m.id === config.colorMode)}
            >
              {m.label}
            </button>
          ))}
        </div>
      )}

      <label style={{ display: 'flex', gap: '4px', alignItems: 'center', fontSize: '10px', color: '#64748b', cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={config.showTraces}
          onChange={(e) => setConfig({ showTraces: e.target.checked })}
          style={{ accentColor: '#f59e0b', margin: 0 }}
        />
        {!compact && 'Traces'}
      </label>

      {wide && (
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#64748b' }}>
          {boardData.components.length} components · {boardData.outline.holes.length} mounting holes
        </span>
      )}
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
