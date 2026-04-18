import { useEffect, useState } from 'react';

export type Breakpoint = 'compact' | 'medium' | 'wide';

const COMPACT_MAX = 768;
const MEDIUM_MAX = 1200;

function getBreakpoint(width: number): Breakpoint {
  if (width < COMPACT_MAX) return 'compact';
  if (width < MEDIUM_MAX) return 'medium';
  return 'wide';
}

export function useBreakpoint(): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(() => getBreakpoint(window.innerWidth));

  useEffect(() => {
    const onResize = () => setBp(getBreakpoint(window.innerWidth));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return bp;
}
