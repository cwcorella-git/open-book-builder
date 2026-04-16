interface Props {
  count: number;
  onClick: () => void;
}

/**
 * Header banner for unresolved build-critical discrepancies. Renders nothing
 * when `count === 0`. Clicking the banner is the canonical way to land on
 * the Discrepancies tab.
 */
export function DiscrepancyBanner({ count, onClick }: Props) {
  if (count === 0) return null;

  const noun = count === 1 ? 'issue' : 'issues';
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        width: '100%',
        padding: '10px 16px',
        background: '#7f1d1d',
        color: '#fee2e2',
        border: 'none',
        borderBottom: '1px solid #ef4444',
        fontSize: '12px',
        cursor: 'pointer',
        textAlign: 'left',
      }}
    >
      <span style={{ fontSize: '14px' }}>⚠</span>
      <span>
        <b style={{ color: '#fef2f2' }}>
          {count} unresolved build-critical {noun}
        </b>
        {' — review before ordering from PCBWay or Digi-Key.'}
      </span>
      <span style={{
        marginLeft: 'auto',
        fontSize: '11px',
        color: '#fca5a5',
        textDecoration: 'underline',
      }}>
        Open Discrepancies ›
      </span>
    </button>
  );
}
