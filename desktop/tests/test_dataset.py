import csv
import io
import json
from pathlib import Path

from open_book_builder.dataset import load_dataset
from open_book_builder.digikey_csv import build_digikey_csv

GOLDEN = Path(__file__).parent / "fixtures" / "board-dataset.golden.json"


def test_sanity_numbers():
    ds = load_dataset(GOLDEN)
    assert len(ds.bom) == 23
    assert ds.per_unit_usd == 43.27
    assert ds.missing_line_items == ["OSO-BOOK-C2-01"]
    assert len(ds.assembly) == 13
    c1, c2 = ds.boards["c1-main"], ds.boards["c2-driver"]
    assert (len(c1["components"]), len(c1["outline"]["holes"]), len(c1["outline"]["edgeSegments"]),
            len(c1["traces"]), len(c1["vias"])) == (27, 4, 40, 296, 76)
    assert (len(c2["components"]), len(c2["outline"]["holes"]), len(c2["outline"]["edgeSegments"]),
            len(c2["traces"]), len(c2["nets"])) == (18, 3, 4, 153, 21)


def test_shipped_dataset_matches_golden():
    assert json.loads(GOLDEN.read_text()) == json.loads(
        (Path(__file__).parents[2] / "data" / "board-dataset.json").read_text()
    )


def test_digikey_csv_matches_web_tool_behaviour():
    ds = load_dataset(GOLDEN)
    result = build_digikey_csv(ds.bom, 10, include_optional=True)
    parsed = list(csv.reader(io.StringIO(result.csv)))
    rows = result.csv.splitlines()
    assert rows[0] == "Digi-Key Part Number,Manufacturer Part Number,Customer Reference,Quantity"
    by_mpn = {r[1]: ",".join(r) for r in parsed[1:]}
    # C2 internals are still exported, as in the web tool (known issue, see docs/).
    assert by_mpn["CL21B105KBFNNNE"].endswith(",90")
    assert by_mpn["CL21A475KAQNNNE"].endswith(",10")
    assert by_mpn["IRLML0100TRPBF"].endswith(",10")
    assert result.csv.endswith("\n")
    no_optional = build_digikey_csv(ds.bom, 1, include_optional=False)
    assert any(s.reason == "optional-excluded" for s in no_optional.skipped)
    assert result.included_count == len(parsed) - 1
