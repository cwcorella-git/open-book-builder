// Assembly view — step checklist on the left, mini 3D viewport + active-step
// detail on the right. The scene-renderer's multi-highlight path (added in
// task #12) dims every component except the active step's `componentRefs`
// so the user can see at a glance which parts they're placing next.
//
// Persistence is localStorage-only via `useAssemblyProgress` (key
// `obb.assemblyStepProgress`).

import { useEffect, useMemo, useState } from 'react';
import { useDataset } from '../lib/dataset-context';
import { useNavigation } from '../lib/navigation-context';
import { useViewport } from '../lib/viewport-context';
import { useBreakpoint, type Breakpoint } from '../lib/use-breakpoint';
import { useAssemblyProgress } from '../lib/use-assembly-progress';
import { BoardViewport } from './BoardViewport';
import type { AssemblyPhase, AssemblyStep } from '../lib/types';

const PHASE_COLOR: Record<AssemblyPhase, string> = {
  'smd-passives': '#2563eb',
  'smd-ics': '#7c3aed',
  'smd-mechanical': '#0891b2',
  tht: '#059669',
  modules: '#d97706',
  mechanical: '#db2777',
  'flash-firmware': '#dc2626',
};

const PHASE_LABEL: Record<AssemblyPhase, string> = {
  'smd-passives': 'Surface-mount: resistors & caps',
  'smd-ics': 'Surface-mount: chips',
  'smd-mechanical': 'Surface-mount: connectors',
  tht: 'Through-hole parts',
  modules: 'Pre-built modules',
  mechanical: 'Mechanical assembly',
  'flash-firmware': 'Software setup',
};

const ACTIVE_ACCENT = '#60a5fa';

export function AssemblyView() {
  const { assembly, boards } = useDataset();
  const { setBoard } = useNavigation();
  const { setConfig } = useViewport();
  const bp = useBreakpoint();
  const compact = bp === 'compact';

  // Sort defensively — assembly.json is already ordered, but keep the view
  // independent of file-ordering drift.
  const orderedSteps = useMemo(
    () => [...assembly].sort((a, b) => a.order - b.order),
    [assembly],
  );

  const progress = useAssemblyProgress(orderedSteps);
  const [hideCompleted, setHideCompleted] = useState(false);

  // Active step is initialized to the first uncompleted one (or null if the
  // user has already finished everything). Lazy initializer so
  // `firstUncompletedStep` only runs on mount.
  const [activeStepId, setActiveStepId] = useState<string | null>(
    () => progress.firstUncompletedStep()?.id ?? null,
  );

  const activeStep = useMemo(
    () => orderedSteps.find((s) => s.id === activeStepId) ?? null,
    [orderedSteps, activeStepId],
  );

  const visibleSteps = useMemo(
    () =>
      hideCompleted
        ? orderedSteps.filter((s) => !progress.isCompleted(s.id))
        : orderedSteps,
    [orderedSteps, hideCompleted, progress],
  );

  // Advance the active step when the current one disappears from view —
  // either because the user ticked it complete while "Hide completed" is on,
  // or because they turned "Hide completed" on while the active step was
  // already completed.
  useEffect(() => {
    if (!activeStep) return;
    if (hideCompleted && progress.isCompleted(activeStep.id)) {
      setActiveStepId(visibleSteps[0]?.id ?? null);
    }
  }, [hideCompleted, activeStep, progress, visibleSteps]);

  // Pass the active step's refs to the shared viewport. 0-ref steps (e.g.
  // "Order PCBs", "Assemble enclosure") pass null → viewport renders normally
  // without any dimming.
  const highlightedRefs =
    activeStep && activeStep.componentRefs.length > 0
      ? activeStep.componentRefs
      : null;

  // Tab activation: lock board to c1-main, disable click-select.
  useEffect(() => {
    setBoard('c1-main');
    setConfig({ clickSelectEnabled: false, visible: true });
  }, [setBoard, setConfig]);

  // Drive viewport highlight and camera focus when the active step changes.
  useEffect(() => {
    setConfig({ highlightedRefs, focusRefs: highlightedRefs });
  }, [highlightedRefs, setConfig]);

  const asideWidth = bp === 'wide' ? '380px' : '300px';

  // Inline viewport for mobile (persistent column is hidden on compact).
  const mobileViewport = compact ? (
    <div style={{ height: '240px', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
      <BoardViewport
        boardData={boards['c1-main']}
        sideFilter="both"
        selectedRef={null}
        onSelect={() => {}}
        highlightedRefs={highlightedRefs}
        focusRefs={highlightedRefs}
      />
    </div>
  ) : null;

  const detailSection = (
    <div style={{ flex: compact ? 'none' : 1, overflow: compact ? undefined : 'auto', minHeight: 0 }}>
      {activeStep ? (
        <ActiveStepPanel step={activeStep} />
      ) : (
        <EmptyActivePanel
          allDone={progress.completedCount === progress.totalCount && progress.totalCount > 0}
        />
      )}
    </div>
  );

  const stepList = (
    <div
      style={{
        flex: 1,
        overflow: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        paddingRight: '4px',
      }}
    >
      {visibleSteps.map((step) => (
        <StepCard
          key={step.id}
          step={step}
          active={step.id === activeStepId}
          completed={progress.isCompleted(step.id)}
          onActivate={() => setActiveStepId(step.id)}
          onToggleCompleted={(v) => progress.setCompleted(step.id, v)}
          bp={bp}
        />
      ))}
      {visibleSteps.length === 0 && (
        <div style={{ color: '#64748b', fontSize: '12px', fontStyle: 'italic', padding: '24px' }}>
          All steps hidden. Untick "Hide completed" to see them again.
        </div>
      )}
    </div>
  );

  if (compact) {
    // On mobile, let the entire page scroll naturally instead of constraining
    // to viewport height with internal scroll regions.
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <ProgressHeader
          completedCount={progress.completedCount}
          totalCount={progress.totalCount}
          totalMinutesRemaining={progress.totalMinutesRemaining}
        />
        <Toolbar
          hideCompleted={hideCompleted}
          setHideCompleted={setHideCompleted}
          visibleCount={visibleSteps.length}
          totalCount={orderedSteps.length}
        />
        {mobileViewport}
        {detailSection}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {visibleSteps.map((step) => (
            <StepCard
              key={step.id}
              step={step}
              active={step.id === activeStepId}
              completed={progress.isCompleted(step.id)}
              onActivate={() => setActiveStepId(step.id)}
              onToggleCompleted={(v) => progress.setCompleted(step.id, v)}
              bp={bp}
            />
          ))}
          {visibleSteps.length === 0 && (
            <div style={{ color: '#64748b', fontSize: '12px', fontStyle: 'italic', padding: '24px' }}>
              All steps hidden. Untick "Hide completed" to see them again.
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: '16px', height: '100%' }}>
      <section
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          gap: '8px',
        }}
      >
        <AssemblyIntro steps={orderedSteps} />
        <ProgressHeader
          completedCount={progress.completedCount}
          totalCount={progress.totalCount}
          totalMinutesRemaining={progress.totalMinutesRemaining}
        />
        <Toolbar
          hideCompleted={hideCompleted}
          setHideCompleted={setHideCompleted}
          visibleCount={visibleSteps.length}
          totalCount={orderedSteps.length}
        />
        {stepList}
      </section>

      <aside
        style={{
          width: asideWidth,
          flexShrink: 0,
          borderLeft: '1px solid #334155',
          paddingLeft: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          minWidth: 0,
          overflow: 'auto',
        }}
      >
        {detailSection}
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------------------

function AssemblyIntro({ steps }: { steps: AssemblyStep[] }) {
  const allTools = useMemo(() => {
    const set = new Set<string>();
    for (const s of steps) for (const t of s.tools) set.add(t);
    return [...set].sort();
  }, [steps]);

  return (
    <div style={{
      fontSize: '12px', color: '#cbd5e1', lineHeight: 1.6,
      paddingBottom: '10px', borderBottom: '1px solid #334155',
    }}>
      <p style={{ margin: 0 }}>
        You're building the Open Book from bare boards to working e-reader. Most of
        the work happens on the <strong style={{ color: '#f1f5f9' }}>Main Board</strong> — the
        E-Paper Driver module arrives pre-assembled from the fab house and gets soldered
        on in one step.
      </p>
      {allTools.length > 0 && (
        <details style={{ marginTop: '8px' }}>
          <summary style={{ cursor: 'pointer', color: '#94a3b8', fontSize: '11px' }}>
            Tools you'll need ({allTools.length})
          </summary>
          <div style={{
            marginTop: '6px', fontSize: '11px', color: '#94a3b8',
            display: 'flex', flexWrap: 'wrap', gap: '4px',
          }}>
            {allTools.map((t) => (
              <span key={t} style={{
                padding: '2px 8px', background: '#0f172a',
                border: '1px solid #1e293b', borderRadius: '3px',
              }}>
                {t}
              </span>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function ProgressHeader({
  completedCount,
  totalCount,
  totalMinutesRemaining,
}: {
  completedCount: number;
  totalCount: number;
  totalMinutesRemaining: number;
}) {
  return (
    <div
      style={{
        fontSize: '12px',
        color: '#cbd5e1',
        paddingBottom: '8px',
        borderBottom: '1px solid #334155',
      }}
    >
      <strong style={{ color: '#f1f5f9' }}>
        {completedCount} of {totalCount} steps complete
      </strong>
      <span style={{ color: '#64748b' }}>
        {' · '}~{totalMinutesRemaining} minutes remaining
      </span>
    </div>
  );
}

function Toolbar({
  hideCompleted,
  setHideCompleted,
  visibleCount,
  totalCount,
}: {
  hideCompleted: boolean;
  setHideCompleted: (v: boolean) => void;
  visibleCount: number;
  totalCount: number;
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: '16px',
        alignItems: 'center',
        flexWrap: 'wrap',
        paddingBottom: '10px',
        borderBottom: '1px solid #334155',
      }}
    >
      <label
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '11px',
          color: '#cbd5e1',
          cursor: 'pointer',
        }}
      >
        <input
          type="checkbox"
          checked={hideCompleted}
          onChange={(e) => setHideCompleted(e.target.checked)}
        />
        Hide completed
      </label>
      <span style={{ marginLeft: 'auto', fontSize: '11px', color: '#64748b' }}>
        {visibleCount === totalCount
          ? `${totalCount} steps`
          : `${visibleCount} of ${totalCount} steps`}
      </span>
    </div>
  );
}

function StepCard({
  step,
  active,
  completed,
  onActivate,
  onToggleCompleted,
  bp = 'wide',
}: {
  step: AssemblyStep;
  active: boolean;
  completed: boolean;
  onActivate: () => void;
  onToggleCompleted: (v: boolean) => void;
  bp?: Breakpoint;
}) {
  const compact = bp === 'compact';
  const wide = bp === 'wide';

  return (
    <div
      onClick={onActivate}
      style={{
        background: active ? '#1e293b' : '#0f172a',
        border: '1px solid ' + (active ? '#475569' : '#1e293b'),
        borderLeft: active ? `3px solid ${ACTIVE_ACCENT}` : '3px solid transparent',
        borderRadius: '6px',
        padding: '10px 12px',
        cursor: 'pointer',
        opacity: completed ? 0.55 : 1,
        display: 'flex',
        flexDirection: 'column',
        gap: active ? '10px' : '4px',
      }}
    >
      <div style={{ display: 'flex', gap: compact ? '6px' : '10px', alignItems: 'center', minWidth: 0 }}>
        <input
          type="checkbox"
          checked={completed}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onToggleCompleted(e.target.checked)}
          style={{ flexShrink: 0 }}
        />
        {wide && <PhasePill phase={step.phase} />}
        <span
          style={{
            fontSize: compact ? '11px' : '12px',
            color: '#e2e8f0',
            flex: 1,
            minWidth: 0,
            textDecoration: completed ? 'line-through' : 'none',
          }}
        >
          {step.title}
        </span>
        {step.estimatedMinutes !== undefined && (
          <span
            style={{
              fontSize: '11px',
              color: '#64748b',
              fontFamily: 'monospace',
              flexShrink: 0,
            }}
          >
            ~{step.estimatedMinutes}min
          </span>
        )}
      </div>

      {!wide && !compact && (
        <div style={{ paddingLeft: '28px' }}>
          <PhasePill phase={step.phase} />
        </div>
      )}

      {active && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingLeft: compact ? '22px' : '28px' }}>
          <div style={{ fontSize: compact ? '11px' : '12px', color: '#cbd5e1', lineHeight: 1.5 }}>
            {step.description}
          </div>
          {step.componentRefs.length > 0 && (
            <ChipRow label="Refs" items={step.componentRefs} monospace />
          )}
          {step.tools.length > 0 && <ChipRow label="Tools" items={step.tools} />}
          {step.notes && (
            <div
              style={{
                fontSize: '11px',
                color: '#94a3b8',
                fontStyle: 'italic',
                borderLeft: '2px solid #334155',
                paddingLeft: '8px',
                lineHeight: 1.5,
              }}
            >
              {step.notes}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ChipRow({
  label,
  items,
  monospace = false,
}: {
  label: string;
  items: string[];
  monospace?: boolean;
}) {
  // When `monospace` is true, items are componentRefs — render them as
  // buttons that jump to the Board tab with that ref pre-selected. Tools
  // chips (monospace=false) stay as inert spans.
  const { navigateToComponent } = useNavigation();
  const chipStyle: React.CSSProperties = {
    padding: '2px 6px',
    fontSize: '11px',
    background: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '3px',
    color: '#cbd5e1',
    fontFamily: monospace ? 'monospace' : undefined,
  };
  return (
    <div style={{ display: 'flex', gap: '8px', alignItems: 'baseline', flexWrap: 'wrap' }}>
      <span style={{ fontSize: '11px', color: '#64748b', flexShrink: 0 }}>{label}</span>
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
        {items.map((item, i) =>
          monospace ? (
            <button
              key={`${item}-${i}`}
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                navigateToComponent(item);
              }}
              style={{ ...chipStyle, cursor: 'pointer', lineHeight: 1.2 }}
              title={`Jump to ${item} on the Board tab`}
            >
              {item}
            </button>
          ) : (
            <span key={`${item}-${i}`} style={chipStyle}>
              {item}
            </span>
          ),
        )}
      </div>
    </div>
  );
}

function PhasePill({ phase }: { phase: AssemblyPhase }) {
  return (
    <span
      style={{
        padding: '2px 6px',
        fontSize: '10px',
        background: PHASE_COLOR[phase],
        color: '#f8fafc',
        borderRadius: '3px',
        letterSpacing: '0.3px',
        flexShrink: 0,
      }}
    >
      {PHASE_LABEL[phase]}
    </span>
  );
}

function ActiveStepPanel({ step }: { step: AssemblyStep }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '12px', color: '#e2e8f0' }}>
      <header style={{ display: 'flex', gap: '8px', alignItems: 'baseline', flexWrap: 'wrap' }}>
        <h2 style={{ fontSize: '13px', color: '#f1f5f9', margin: 0, lineHeight: 1.3 }}>
          {step.title}
        </h2>
        <PhasePill phase={step.phase} />
      </header>

      <div style={{ color: '#cbd5e1', lineHeight: 1.5 }}>{step.description}</div>

      {step.componentRefs.length > 0 ? (
        <ChipRow label="Highlighted" items={step.componentRefs} monospace />
      ) : (
        <div style={{ fontSize: '11px', color: '#64748b', fontStyle: 'italic' }}>
          No PCB components highlighted — this step is instructional or mechanical.
        </div>
      )}

      {step.tools.length > 0 && <ChipRow label="Tools" items={step.tools} />}

      {step.estimatedMinutes !== undefined && (
        <div style={{ fontSize: '11px', color: '#64748b' }}>
          Estimated time: ~{step.estimatedMinutes} minutes
        </div>
      )}

      {step.notes && (
        <div
          style={{
            fontSize: '11px',
            color: '#94a3b8',
            fontStyle: 'italic',
            borderLeft: '2px solid #334155',
            paddingLeft: '8px',
            lineHeight: 1.5,
          }}
        >
          {step.notes}
        </div>
      )}
    </div>
  );
}

function EmptyActivePanel({ allDone }: { allDone: boolean }) {
  return (
    <div
      style={{
        padding: '24px 8px',
        color: '#64748b',
        fontSize: '12px',
        fontStyle: 'italic',
        lineHeight: 1.5,
      }}
    >
      {allDone
        ? 'All steps complete. Time to turn the page.'
        : 'Click a step on the left to see its details. The viewport above highlights the components it touches.'}
    </div>
  );
}
