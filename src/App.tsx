import { useState } from 'react';
import { DatasetProvider, useDatasetStatus } from './lib/dataset-context';
import { useDiscrepancyResolution } from './lib/use-discrepancy-resolution';
import { BoardView } from './components/BoardView';
import { BomView } from './components/BomView';
import { DiscrepancyView } from './components/DiscrepancyView';
import { DiscrepancyBanner } from './components/DiscrepancyBanner';

type Tab = 'board' | 'bom' | 'assembly' | 'discrepancies';

const TABS: { id: Tab; label: string }[] = [
  { id: 'board', label: 'Board' },
  { id: 'bom', label: 'BOM' },
  { id: 'assembly', label: 'Assembly' },
  { id: 'discrepancies', label: 'Discrepancies' },
];

function Shell() {
  const [tab, setTab] = useState<Tab>('bom');
  const status = useDatasetStatus();

  // Hook must be called unconditionally; feed empty array when not ready.
  const discrepancies =
    status.kind === 'ready' ? status.dataset.discrepancies : [];
  const { unresolvedBuildCritical } = useDiscrepancyResolution(discrepancies);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%', width: '100%',
    }}>
      <header style={{
        display: 'flex', alignItems: 'center', gap: '16px',
        padding: '10px 16px', borderBottom: '1px solid #334155', background: '#1e293b',
      }}>
        <h1 style={{ fontSize: '14px', letterSpacing: '0.5px', color: '#f1f5f9' }}>
          Open Book Builder
        </h1>
        <nav style={{ display: 'flex', gap: '4px' }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
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
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#64748b' }}>
          {status.kind === 'loading' && 'Loading dataset…'}
          {status.kind === 'error' && `Error: ${status.message}`}
          {status.kind === 'ready' &&
            `${status.dataset.bom.length} BOM rows · ${status.dataset.discrepancies.length} discrepancies`}
        </span>
      </header>

      <DiscrepancyBanner
        count={unresolvedBuildCritical.length}
        onClick={() => setTab('discrepancies')}
      />

      <main style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        {status.kind === 'loading' && <Placeholder text="Loading…" />}
        {status.kind === 'error' && <Placeholder text={`Error loading dataset: ${status.message}`} />}
        {status.kind === 'ready' && <TabContent tab={tab} />}
      </main>
    </div>
  );
}

function TabContent({ tab }: { tab: Tab }) {
  switch (tab) {
    case 'board': return <BoardView />;
    case 'bom': return <BomView />;
    case 'assembly': return <Placeholder text="Assembly checklist lands in task #12." />;
    case 'discrepancies': return <DiscrepancyView />;
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
      <Shell />
    </DatasetProvider>
  );
}
