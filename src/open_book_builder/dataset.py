"""Load the board dataset (BOM, assembly steps, board geometry, cost summary)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

BOARD_LABELS = {"c1-main": "C1 main", "c2-driver": "C2 driver"}


@dataclass
class BomLine:
    refs: list[str]
    qty: int
    description: str
    mpn: str
    board: str
    optional: bool = False
    manufacturer: str | None = None
    digikey_pn: str | None = None
    mouser_pn: str | None = None
    lcsc_pn: str | None = None
    unit_cost_usd: float | None = None
    footprint: str | None = None
    function: str = ""
    datasheet_url: str | None = None
    route_detail: bool = False
    price_status: str | None = None
    in_stock: bool | None = None
    offers: list[dict] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.board}:{','.join(self.refs)}:{self.mpn}"


@dataclass
class AssemblyStep:
    id: str
    order: int
    phase: str
    title: str
    description: str
    board: str
    component_refs: list[str] = field(default_factory=list)
    estimated_minutes: int | None = None
    tools: list[str] = field(default_factory=list)
    notes: str | None = None
    untested: bool = False
    deferred: bool = False


@dataclass
class Dataset:
    bom: list[BomLine]
    assembly: list[AssemblyStep]
    per_unit_usd: float
    missing_line_items: list[str]
    boards: dict
    unavailable_line_items: list[str] = field(default_factory=list)


def find_data_dir() -> Path:
    """Search upward from this file for the data/ folder (it holds bom-c1-main.csv)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "data" / "bom-c1-main.csv").is_file():
            return parent / "data"
    raise FileNotFoundError("The data folder was not found. Run the app from a checkout of the repository.")


def load_dataset(path: Path | None = None) -> Dataset:
    """Build the dataset from the files in data/, or read a baked JSON file when `path` is given."""
    if path is None:
        from .build.dataset_build import build_dataset

        raw = build_dataset(find_data_dir())
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))
    bom = [
        BomLine(
            refs=b["refs"],
            qty=b["qty"],
            description=b["description"],
            mpn=b["mpn"],
            board=b["board"],
            optional=b.get("optional", False),
            manufacturer=b.get("manufacturer"),
            digikey_pn=b.get("digikeyPn"),
            mouser_pn=b.get("mouserPn"),
            lcsc_pn=b.get("lcscPn"),
            unit_cost_usd=b.get("unitCostUsd"),
            footprint=b.get("footprint"),
            function=b.get("function", ""),
            datasheet_url=b.get("datasheetUrl"),
            route_detail=b.get("routeDetail", False),
            price_status=b.get("priceStatus"),
            in_stock=b.get("inStock"),
            offers=b.get("offers", []),
        )
        for b in raw["bom"]
    ]
    assembly = sorted(
        (
            AssemblyStep(
                id=a["id"],
                order=a["order"],
                phase=a["phase"],
                title=a["title"],
                description=a["description"],
                board=a["board"],
                component_refs=a.get("componentRefs", []),
                estimated_minutes=a.get("estimatedMinutes"),
                tools=a.get("tools", []),
                notes=a.get("notes"),
                untested=a.get("untested", False),
                deferred=a.get("deferred", False),
            )
            for a in raw["assembly"]
        ),
        key=lambda s: s.order,
    )
    cost = raw["costSummary"]
    return Dataset(
        bom=bom,
        assembly=assembly,
        per_unit_usd=round(cost["perUnitUsd"], 2),
        missing_line_items=cost["missingLineItems"],
        boards=raw["boards"],
        unavailable_line_items=cost.get("unavailableLineItems", []),
    )


def load_checklist(data_dir: Path | None = None) -> list[dict]:
    """Checklist items that are not BOM lines (boards, cards, fees, tools)."""
    path = (data_dir or find_data_dir()) / "checklist.json"
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def source_name(line: BomLine) -> str:
    """Where a part is bought, from its first dated offer, else from the supplier part numbers."""
    if line.offers:
        return line.offers[0]["supplier"]
    if line.digikey_pn:
        return "Digi-Key"
    return "Open"
