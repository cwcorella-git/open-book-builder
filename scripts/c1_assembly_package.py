#!/usr/bin/env python3
"""Write a placement file and an assembly BOM for the C1 main board, for a factory quote.

Reads data/OSO-BOOK-C1.kicad_pcb and the BOM, and writes two CSV files. Run from the
repository root:  uv run python scripts/c1_assembly_package.py [output-folder]

What is derived and what is not is written up in docs/c1-assembly-package.md.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from open_book_builder.build import bom as bom_mod
from open_book_builder.build import sexpr
from open_book_builder.build.sexpr import find_all_tagged, find_tagged, head, positional
from open_book_builder.dataset import find_data_dir

# How each part is expected to be fitted. The factory decides what it will actually place.
ROUTE = {
    "SMD": "SMD, a factory can place it",
    "THT": "Through-hole, usually hand work or a separate factory step",
    "MECH": "Large or mechanical part: ask the factory before assuming it is placed",
    "MODULE": "Module soldered on by its castellated edge: hand work",
}
MECH_REFS = {"BT1", "U1", "U3"}  # battery holder, Pico, microSD socket
MODULE_REFS = {"U2"}


def read_footprints(pcb: Path) -> list[dict]:
    text = re.sub(r"\((?:tstamp|tedit) [^()]*\)", "", pcb.read_text(encoding="utf-8"))
    root = sexpr.parse(text)
    out = []
    for fp in positional(root):
        if head(fp) != "footprint":
            continue
        ref = value = None
        for t in find_all_tagged(fp, "fp_text"):
            a = positional(t)
            if a and a[0] == "reference":
                ref = a[1]
            elif a and a[0] == "value":
                value = a[1]
        name = positional(fp)[0]
        if not ref or ref.startswith(("REF", "G*")) or name.startswith(("MountingHole", "Jumper:SolderJumper")):
            continue  # artwork, mounting holes and open solder jumpers (JP1, JP2) have no part to place
        at = positional(find_tagged(fp, "at"))
        layer = positional(find_tagged(fp, "layer"))[0]
        pads = find_all_tagged(fp, "pad")
        through = any(str(positional(p)[1]) == "thru_hole" for p in pads)
        out.append({"ref": ref, "value": value or "", "footprint": positional(fp)[0], "x": float(at[0]),
                    "y": float(at[1]), "rot": float(at[2]) if len(at) > 2 else 0.0,
                    "side": "Bottom" if layer == "B.Cu" else "Top", "through": through})
    return out


def route_of(fp: dict) -> str:
    if fp["ref"] in MODULE_REFS:
        return "MODULE"
    if fp["ref"] in MECH_REFS:
        return "MECH"
    return "THT" if fp["through"] else "SMD"


def main(argv: list[str]) -> int:
    data = find_data_dir()
    out_dir = Path(argv[0]) if argv else data.parent / "docs" / "c1-assembly-package"
    out_dir.mkdir(parents=True, exist_ok=True)
    bom = [l for l in bom_mod.load_all(data) if l["board"] == "c1-main"]
    by_ref = {r: l for l in bom for r in l["refs"]}
    fps = sorted(read_footprints(data / "OSO-BOOK-C1.kicad_pcb"), key=lambda f: (f["ref"][0], int(re.sub(r"\D", "", f["ref"]) or 0)))

    with (out_dir / "c1-placement.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["Designator", "Footprint", "Mid X (mm)", "Mid Y (mm)", "Rotation", "Layer", "Fit"])
        for f in fps:
            # Y is flipped to the y-up convention factories expect. X and Y are the footprint origin, not its centre.
            w.writerow([f["ref"], f["footprint"], f"{f['x']:.4f}", f"{-f['y']:.4f}", f"{f['rot']:g}", f["side"], route_of(f)])

    rows = {}
    for f in fps:
        line = by_ref.get(f["ref"])
        if line is None:
            continue
        rows.setdefault(line["mpn"], {"line": line, "refs": [], "fits": set()})
        rows[line["mpn"]]["refs"].append(f["ref"])
        rows[line["mpn"]]["fits"].add(route_of(f))
    with (out_dir / "c1-assembly-bom.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["Comment", "Designator", "Footprint", "MPN", "Digi-Key", "LCSC Part #", "Fit", "Optional", "Gap"])
        for mpn, r in rows.items():
            line = r["line"]
            fp = next(f for f in fps if f["ref"] == r["refs"][0])
            gaps = []
            if not line.get("lcscPn"):
                gaps.append("no LCSC number recorded")
            if not line.get("digikeyPn"):
                gaps.append("no Digi-Key number recorded")
            fit = "; ".join(ROUTE[k] for k in sorted(r["fits"]))
            w.writerow([line["description"], ",".join(r["refs"]), fp["footprint"], mpn, line.get("digikeyPn") or "",
                        line.get("lcscPn") or "", fit, "yes" if line["optional"] else "no", "; ".join(gaps)])
        missing = [l for l in bom if not any(ref in {f["ref"] for f in fps} for ref in l["refs"])]
        for line in missing:
            w.writerow([line["description"], ",".join(line["refs"]), "", line["mpn"], line.get("digikeyPn") or "",
                        line.get("lcscPn") or "", "Not on the board file: buy and fit separately", "no", "not placed by a factory"])
    print(f"Wrote {len(fps)} placements and {len(rows)} BOM lines to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
