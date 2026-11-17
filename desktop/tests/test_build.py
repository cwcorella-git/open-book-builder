"""The Python build must reproduce the golden dataset made by the web tool's Rust code."""
import json
import math
from pathlib import Path

import pytest

from open_book_builder.build import bom as bom_mod
from open_book_builder.build import kicad_pcb

ROOT = Path(__file__).parents[2]
SRC = ROOT / "src-tauri" / "data"
GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "board-dataset.golden.json").read_text())


def close(a, b, path="$"):
    """Deep compare; floats within 1e-3 (the Rust code used f32)."""
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, abs_tol=1e-3):
            return
        raise AssertionError(f"{path}: {a!r} != {b!r}")
    if isinstance(a, dict) and isinstance(b, dict):
        assert a.keys() == b.keys(), f"{path}: keys {sorted(set(a) ^ set(b))}"
        for k in a:
            close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f"{path}[{i}]")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


def strip_none(d):
    return {k: v for k, v in d.items() if v is not None}


def test_bom_matches_golden():
    bom = [strip_none(l) for l in bom_mod.load_all(SRC)]
    close(bom, GOLDEN["bom"])


def test_cost_summary_matches_golden():
    bom = bom_mod.load_all(SRC)
    close(bom_mod.summarize_cost(bom), GOLDEN["costSummary"])


def test_c1_board_matches_golden():
    bom = bom_mod.load_all(SRC)
    board = kicad_pcb.load_c1_board(SRC / "OSO-BOOK-C1.kicad_pcb", bom)
    close(board, GOLDEN["boards"]["c1-main"])


def test_c2_board_matches_golden():
    from open_book_builder.build import eagle
    bom = bom_mod.load_all(SRC)
    board = eagle.load_c2_board(SRC / "OSO-BOOK-C2-02.brd", bom)
    close(board, GOLDEN["boards"]["c2-driver"])


def test_full_dataset_matches_golden():
    from open_book_builder.build.dataset_build import build_dataset
    close(build_dataset(SRC), GOLDEN)


def test_comparison_is_not_vacuous():
    broken = json.loads(json.dumps(GOLDEN))
    broken["boards"]["c2-driver"]["traces"][0]["width"] += 0.5
    with pytest.raises(AssertionError):
        close(broken, GOLDEN)
