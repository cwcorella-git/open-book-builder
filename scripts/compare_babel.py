#!/usr/bin/env python3
"""Compare two babel.bin files field by field (for the code points both list), as a check on build_babel.py.

  compare_babel.py mine.bin original.bin

Differences that come from different Unifont or Unicode versions (glyph shapes, a few reclassified characters,
added case and mirroring pairs) show up here and are expected; anything else is a bug.
"""
from __future__ import annotations

import collections
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("build_babel", Path(__file__).with_name("build_babel.py"))
bb = importlib.util.module_from_spec(spec)
sys.modules["build_babel"] = bb
spec.loader.exec_module(bb)

FIELDS = {27: "non-spacing", 28: "strong rtl", 29: "strong ltr", 30: "control", 31: "line break"}
MASKS = ((0x1F, "category"), (0xE0, "case flags"), (0xF00, "bidi class"), (0x1000, "mirror flag"), (0x2000, "whitespace"))


def compare(mine: bytes, other: bytes) -> dict:
    a, b = bb.BabelReader(mine), bb.BabelReader(other)
    both = [cp for cp in range(0x10000) if a.info(cp) and b.info(cp)]
    diffs = collections.defaultdict(list)
    for cp in both:
        ia, ib = a.info(cp), b.info(cp)
        if (ia >> 22) & 31 != (ib >> 22) & 31:
            diffs["width"].append(cp)
        for bit, name in FIELDS.items():
            if (ia >> bit) & 1 != (ib >> bit) & 1:
                diffs[name].append(cp)
        ea, eb = a.extended(cp), b.extended(cp)
        for mask, name in MASKS:
            if ea & mask != eb & mask:
                diffs[name].append(cp)
        if a.glyph(cp) != b.glyph(cp):
            diffs["glyph bitmap"].append(cp)
    for kind, name in ((1, "upper case"), (2, "lower case"), (3, "title case"), (4, "mirroring")):
        x, y = a.mapping(kind), b.mapping(kind)
        diffs[f"{name}: only in first"] = sorted(set(x) - set(y))
        diffs[f"{name}: only in second"] = sorted(set(y) - set(x))
        diffs[f"{name}: different value"] = [c for c in set(x) & set(y) if x[c] != y[c]]
    return {"shared": len(both), "diffs": {k: v for k, v in diffs.items() if v}}


def main(argv: list[str] | None = None) -> int:
    first, second = (Path(p).read_bytes() for p in (argv or sys.argv[1:])[:2])
    result = compare(first, second)
    print(f"{result['shared']} code points listed in both files.")
    for name, cps in result["diffs"].items():
        print(f"{name}: {len(cps)} (for example {', '.join(f'U+{c:04X}' for c in sorted(cps)[:6])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
