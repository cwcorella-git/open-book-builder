"""BOM CSV parsing, per-MPN metadata merge and cost summary (port of bom.rs)."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

C2_FOOTPRINT_HEADERS = ("*Package/Footprint ", "*Package/Footprint")  # PCBWay's header has a trailing space


def split_refs(raw: str) -> list[str]:
    return [r.strip() for r in raw.split(",") if r.strip()]


def is_optional(description: str) -> bool:
    return "OPTIONAL" in description.upper()


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _lookup(data_dir: Path) -> dict:
    raw = json.loads((data_dir / "component_functions.json").read_text(encoding="utf-8"))
    raw.pop("_comment", None)
    return raw


def _apply_lookup(line: dict, lookup: dict) -> None:
    cf = lookup.get(line["mpn"])
    if cf is None:
        line["function"] = line["description"]
        return
    line["function"] = cf["function"]
    for src, dst in (("datasheetUrl", "datasheetUrl"), ("unitCostUsd", "unitCostUsd"), ("heroMeshId", "heroMeshId")):
        if cf.get(src) is not None:
            line[dst] = cf[src]
    for key in ("digikeyPn", "mouserPn", "lcscPn"):
        if line.get(key) is None and cf.get(key) is not None:
            line[key] = cf[key]


def _base(refs, qty, description, manufacturer, mpn, board) -> dict:
    return {"refs": refs, "qty": qty, "description": description, "manufacturer": manufacturer, "mpn": mpn,
            "optional": is_optional(description), "function": "", "board": board}


def _offers(data_dir: Path) -> dict[str, list[dict]]:
    path = data_dir / "offers.json"
    if not path.is_file():
        return {}
    out: dict[str, list[dict]] = {}
    for offer in json.loads(path.read_text(encoding="utf-8"))["offers"]:
        out.setdefault(offer["mpn"], []).append(offer)
    return out


def _apply_offers(line: dict, offers: dict[str, list[dict]]) -> None:
    """The first offer for a part sets its unit price. Parts without one keep an undated estimate."""
    mine = offers.get(line["mpn"])
    if mine:
        line["offers"] = mine
        line["unitCostUsd"] = mine[0]["unitPriceUsd"]
        line["priceStatus"] = mine[0]["status"]
        line["inStock"] = mine[0].get("inStock")
    elif line.get("unitCostUsd") is not None:
        line["priceStatus"] = "estimate"


def _rows(path: Path):
    return csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))


def load_all(data_dir: Path) -> list[dict]:
    lookup = _lookup(data_dir)
    offers = _offers(data_dir)
    out: list[dict] = []
    for row in _rows(data_dir / "bom-c1-main.csv"):
        line = _base(split_refs(row["References"]), int(row["Qty"]), row["Description"],
                     _clean(row["Manufacturer"]), row["MPN"], "c1-main")
        line["digikeyPn"] = _clean(row["Digikey"])
        line["mouserPn"] = _clean(row["Mouser"])
        _apply_lookup(line, lookup)
        _apply_offers(line, offers)
        out.append(line)
    for row in _rows(data_dir / "bom-c2-driver.csv"):
        footprint = next((row[h] for h in C2_FOOTPRINT_HEADERS if h in row), "")
        line = _base(split_refs(row["*Designator"]), int(row["*Qty"]), row["Description / Value"],
                     _clean(row["Manufacturer"]), row["*Mfg Part #"], "c2-driver")
        line["footprint"] = _clean(footprint)
        line["routeDetail"] = True  # inside the pre-assembled C2 module (OSO-BOOK-C2-01), not bought on its own
        _apply_lookup(line, lookup)
        _apply_offers(line, offers)
        out.append(line)
    return out


def summarize_cost(bom: list[dict]) -> dict:
    """Per-unit sum over non-optional C1 lines. C2 internals are excluded on purpose:
    the driver module is priced as one PCBA (OSO-BOOK-C2-01). Lines whose first offer shows no stock are
    still priced but listed in unavailableLineItems."""
    per_unit, missing, unavailable = 0.0, [], []
    for line in bom:
        if line["optional"] or line["board"] == "c2-driver":
            continue
        price = line.get("unitCostUsd")
        if price is None:
            missing.append(line["mpn"])
        else:
            per_unit += price * line["qty"]
            if line.get("inStock") is False:
                unavailable.append(line["mpn"])
    return {"perUnitUsd": per_unit, "missingLineItems": missing, "unavailableLineItems": unavailable}
