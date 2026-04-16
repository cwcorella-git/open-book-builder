import type { BomLine } from './types';

/**
 * Pure generator for Digi-Key BOM Manager CSV.
 *
 * Format (per Digi-Key's template at https://www.digikey.com/BOM):
 *
 *   Digi-Key Part Number,Manufacturer Part Number,Customer Reference,Quantity
 *   2648-SC0918CT-ND,SC0918,U1,1
 *   311-1.00KARCT-ND,RC0805FR-071KL,"R1,R2,R3",3
 *
 * A line is SKIPPED when:
 *   - It has no `digikeyPn` (Digi-Key can't look it up — e.g. C2 internals,
 *     the GDEW042T2 panel ordered direct from Good Display, the
 *     OSO-BOOK-C2-01 module self-sourced from the C2 PCBA order).
 *   - `optional === true` and `opts.includeOptional === false`.
 *
 * The board filter is intentionally ignored: it's a view concern, and all
 * C2-driver lines skip anyway (none have `digikeyPn`), so C1-only and
 * Both-boards produce identical CSVs.
 */

export type SkipReason = 'no-digikey-pn' | 'optional-excluded';

export interface SkippedLine {
  mpn: string;
  refs: string[];
  reason: SkipReason;
}

export interface CsvBuildResult {
  /** Full CSV text including header row and trailing newline. */
  csv: string;
  /** Number of data rows written (excludes the header). */
  includedCount: number;
  /** Lines that were dropped, with reason. Preserves input order. */
  skipped: SkippedLine[];
}

export interface CsvBuildOptions {
  qtyMultiplier: number;
  includeOptional: boolean;
}

const HEADER = 'Digi-Key Part Number,Manufacturer Part Number,Customer Reference,Quantity';

/**
 * CSV-escape per RFC 4180: if the field contains `,`, `"`, CR, or LF,
 * wrap in double quotes and double any embedded double quotes.
 */
function csvField(value: string): string {
  if (/[",\r\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

export function buildDigiKeyCsv(
  bom: BomLine[],
  opts: CsvBuildOptions,
): CsvBuildResult {
  const multiplier = Math.max(1, Math.floor(opts.qtyMultiplier));
  const lines: string[] = [HEADER];
  const skipped: SkippedLine[] = [];
  let includedCount = 0;

  for (const line of bom) {
    if (!line.digikeyPn) {
      skipped.push({ mpn: line.mpn, refs: line.refs, reason: 'no-digikey-pn' });
      continue;
    }
    if (line.optional && !opts.includeOptional) {
      skipped.push({ mpn: line.mpn, refs: line.refs, reason: 'optional-excluded' });
      continue;
    }

    const refsJoined = line.refs.join(',');
    const qty = line.qty * multiplier;
    lines.push([
      csvField(line.digikeyPn),
      csvField(line.mpn),
      csvField(refsJoined),
      String(qty),
    ].join(','));
    includedCount += 1;
  }

  return {
    csv: lines.join('\n') + '\n',
    includedCount,
    skipped,
  };
}

/**
 * Fast count for the toolbar subtitle — runs every render. Avoids allocating
 * the full CSV string when only the summary is needed.
 */
export function summarizeExport(
  bom: BomLine[],
  includeOptional: boolean,
): { includedCount: number; skippedCount: number } {
  let includedCount = 0;
  let skippedCount = 0;
  for (const line of bom) {
    if (!line.digikeyPn) {
      skippedCount += 1;
    } else if (line.optional && !includeOptional) {
      skippedCount += 1;
    } else {
      includedCount += 1;
    }
  }
  return { includedCount, skippedCount };
}
