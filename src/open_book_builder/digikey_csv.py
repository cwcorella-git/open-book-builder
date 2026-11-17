"""Digi-Key BOM Manager CSV export (port of the web tool's digikey-csv.ts).

A line is skipped when it is inside the pre-assembled C2 module, has no Digi-Key
part number, or is optional while optional parts are excluded. The board filter
is ignored on purpose.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from .dataset import BomLine

HEADER = ["Digi-Key Part Number", "Manufacturer Part Number", "Customer Reference", "Quantity"]


@dataclass
class SkippedLine:
    mpn: str
    refs: list[str]
    reason: str  # "inside-module", "no-digikey-pn" or "optional-excluded"


@dataclass
class CsvResult:
    csv: str
    included_count: int
    skipped: list[SkippedLine]


def build_digikey_csv(bom: list[BomLine], qty_multiplier: int, include_optional: bool) -> CsvResult:
    multiplier = max(1, int(qty_multiplier))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    skipped: list[SkippedLine] = []
    included = 0
    for line in bom:
        if line.route_detail:
            skipped.append(SkippedLine(line.mpn, line.refs, "inside-module"))
            continue
        if not line.digikey_pn:
            skipped.append(SkippedLine(line.mpn, line.refs, "no-digikey-pn"))
            continue
        if line.optional and not include_optional:
            skipped.append(SkippedLine(line.mpn, line.refs, "optional-excluded"))
            continue
        writer.writerow([line.digikey_pn, line.mpn, ",".join(line.refs), line.qty * multiplier])
        included += 1
    return CsvResult(out.getvalue(), included, skipped)
