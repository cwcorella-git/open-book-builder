import { useCallback } from 'react';
import { DatasetProvider, useDataset, useDatasetStatus } from './lib/dataset-context';
import { NavigationProvider, useNavigation, type Tab } from './lib/navigation-context';
import { ViewportProvider, useViewport } from './lib/viewport-context';
import { useBreakpoint } from './lib/use-breakpoint';
import { BoardViewport } from './components/BoardViewport';
import { ViewportToolbar } from './components/ViewportToolbar';
import { BoardView } from './components/BoardView';
import { BomView } from './components/BomView';
import { AssemblyView } from './components/AssemblyView';
import { AboutView } from './components/AboutView';

const TABS: { id: Tab; label: string }[] = [
  { id: 'board', label: 'Board' },
  { id: 'bom', label: 'Parts List' },
  { id: 'assembly', label: 'Assembly' },
  { id: 'about', label: 'About' },
];

const noop = () => {};

function ViewportColumn() {
  const { config } = useViewport();
  const { board, selectedRef, selectComponent } = useNavigation();
  const dataset = useDataset();
  const boardData = dataset.boards[board];

  const onSelect = useCallback(
    (ref: string | null) => {
      if (config.clickSelectEnabled) selectComponent(ref);
    },
    [config.clickSelectEnabled, selectComponent],
  );

  return (
    <section style={{
      flex: '0 0 58%',
      display: 'flex',
      flexDirection: 'column',
      minWidth: 0,
      minHeight: 0,
      padding: '16px 0 16px 16px',
    }}>
      <ViewportToolbar />
      <BoardViewport
        boardData={boardData}
        sideFilter={config.sideFilter}
        selectedRef={selectedRef}
        onSelect={config.clickSelectEnabled ? onSelect : noop}
        highlightedRefs={config.highlightedRefs}
        colorMode={config.colorMode}
        showTraces={config.showTraces}
        focusRefs={config.focusRefs}
      />
    </section>
  );
}

function Shell() {
  const { tab, setTab } = useNavigation();
  const { config } = useViewport();
  const status = useDatasetStatus();
  const bp = useBreakpoint();
  const compact = bp === 'compact';

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%', width: '100%',
    }}>
      <header style={{
        display: 'flex', alignItems: 'center', gap: compact ? '8px' : '16px',
        padding: compact ? '8px 10px' : '10px 16px',
        borderBottom: '1px solid #334155', background: '#1e293b',
        flexWrap: 'wrap',
      }}>
        <h1 style={{ fontSize: compact ? '13px' : '14px', letterSpacing: '0.5px', color: '#f1f5f9', whiteSpace: 'nowrap' }}>
          Open Book Builder
        </h1>
        <nav style={{ display: 'flex', gap: '4px' }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: compact ? '5px 8px' : '6px 12px',
                fontSize: compact ? '11px' : '12px',
                background: t.id === tab ? '#334155' : 'transparent',
                color: '#e2e8f0',
                border: '1px solid ' + (t.id === tab ? '#475569' : 'transparent'),
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>
        {!compact && (
          <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#64748b' }}>
            {status.kind === 'loading' && 'Loading dataset\u2026'}
            {status.kind === 'error' && `Error: ${status.message}`}
            {status.kind === 'ready' && `${status.dataset.bom.length} parts`}
          </span>
        )}
      </header>

      {status.kind === 'loading' && (
        <main style={{ flex: 1, overflow: 'auto', padding: compact ? '10px' : '16px' }}>
          <Placeholder text="Loading\u2026" />
        </main>
      )}
      {status.kind === 'error' && (
        <main style={{ flex: 1, overflow: 'auto', padding: compact ? '10px' : '16px' }}>
          <Placeholder text={`Error loading dataset: ${status.message}`} />
        </main>
      )}
      {status.kind === 'ready' && (
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {config.visible && !compact && <ViewportColumn />}
          <main style={{ flex: 1, overflow: 'auto', padding: compact ? '10px' : '16px' }}>
            <TabContent tab={tab} />
          </main>
        </div>
      )}
    </div>
  );
}

function TabContent({ tab }: { tab: Tab }) {
  switch (tab) {
    case 'board': return <BoardView />;
    case 'bom': return <BomView />;
    case 'assembly': return <AssemblyView />;
    case 'about': return <AboutView />;
  }
}

function Placeholder({ text }: { text: string }) {
  return (
    <div style={{
      padding: '40px',
      textAlign: 'center',
      color: '#94a3b8',
      fontSize: '13px',
      border: '1px dashed #334155',
      borderRadius: '8px',
    }}>
      {text}
    </div>
  );
}

export default function App() {
  return (
    <DatasetProvider>
      <NavigationProvider>
        <ViewportProvider>
          <Shell />
        </ViewportProvider>
      </NavigationProvider>
    </DatasetProvider>
  );
}
