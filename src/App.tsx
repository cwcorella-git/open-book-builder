import { DatasetProvider, useDatasetStatus } from './lib/dataset-context';
import { NavigationProvider, useNavigation, type Tab } from './lib/navigation-context';
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

function Shell() {
  const { tab, setTab } = useNavigation();
  const status = useDatasetStatus();

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
          {status.kind === 'ready' && `${status.dataset.bom.length} parts`}
        </span>
      </header>

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
        <Shell />
      </NavigationProvider>
    </DatasetProvider>
  );
}
