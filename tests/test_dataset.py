import csv
import io
import json
from pathlib import Path

from open_book_builder.dataset import load_dataset
from open_book_builder.digikey_csv import build_digikey_csv

GOLDEN = Path(__file__).parent / "fixtures" / "board-dataset.golden.json"


def test_sanity_numbers():
    ds = load_dataset(GOLDEN)
    assert len(ds.bom) == 24
    assert ds.per_unit_usd == 32.53
    assert ds.missing_line_items == ["OSO-BOOK-C2-01"]
    assert ds.unavailable_line_items == ["GDEY042T81"]
    assert len(ds.assembly) == 13
    c1, c2 = ds.boards["c1-main"], ds.boards["c2-driver"]
    assert (len(c1["components"]), len(c1["outline"]["holes"]), len(c1["outline"]["edgeSegments"]),
            len(c1["traces"]), len(c1["vias"])) == (27, 4, 40, 296, 76)
    assert (len(c2["components"]), len(c2["outline"]["holes"]), len(c2["outline"]["edgeSegments"]),
            len(c2["traces"]), len(c2["nets"])) == (18, 3, 4, 153, 21)


def test_default_load_builds_from_source_files():
    built = load_dataset()
    golden = load_dataset(GOLDEN)
    assert built.per_unit_usd == golden.per_unit_usd == 32.53
    assert [b.mpn for b in built.bom] == [b.mpn for b in golden.bom]
    assert [a.id for a in built.assembly] == [a.id for a in golden.assembly]


def test_digikey_csv_leaves_out_c2_internals():
    ds = load_dataset(GOLDEN)
    result = build_digikey_csv(ds.bom, 10, include_optional=True)
    parsed = list(csv.reader(io.StringIO(result.csv)))
    assert parsed[0] == ["Digi-Key Part Number", "Manufacturer Part Number", "Customer Reference", "Quantity"]
    exported = {r[1] for r in parsed[1:]}
    for mpn in ("CL21B105KBFNNNE", "CL21A475KAQNNNE", "IRLML0100TRPBF"):
        assert mpn not in exported  # inside the pre-assembled C2 module
    assert sum(s.reason == "inside-module" for s in result.skipped) == 7
    assert {"1022C", "1022"} <= exported
    assert "SC0915" not in exported  # no Digi-Key number recorded yet, so it is skipped
    assert any(s.mpn == "SC0915" and s.reason == "no-digikey-pn" for s in result.skipped)
    assert result.csv.endswith("\n")
    no_optional = build_digikey_csv(ds.bom, 1, include_optional=False)
    assert any(s.reason == "optional-excluded" for s in no_optional.skipped)
    assert result.included_count == len(parsed) - 1


def test_review_corrections_are_in_the_data():
    ds = load_dataset(GOLDEN)
    mpns = {b.mpn for b in ds.bom}
    assert "SC0918" not in mpns and "GDEW042T2" not in mpns
    assert {"SC0915", "1022C", "GDEY042T81"} <= mpns
    clip = next(b for b in ds.bom if b.mpn == "1022C")
    assert clip.unit_cost_usd == 0.75 and clip.price_status == "listed"
    display = next(b for b in ds.bom if b.mpn == "GDEY042T81")
    assert display.in_stock is False and display.offers[0]["observed"] == "2026-11-15"
    assert sum(b.route_detail for b in ds.bom) == 7
    steps = {a.id: a for a in ds.assembly}
    assert steps["flash-firmware"].untested and "PlatformIO" in steps["flash-firmware"].description
    assert "Pico SDK" not in steps["flash-firmware"].description
    assert steps["assemble-enclosure"].deferred
    assert steps["prepare-sd-card"].order < steps["flash-firmware"].order < steps["flash-babel"].order
