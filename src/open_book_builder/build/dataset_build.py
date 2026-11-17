"""Build the dataset dict (same shape as board-dataset.json) from the source files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import bom as bom_mod
from . import eagle, kicad_pcb


def find_source_dir() -> Path:
    """The folder with bom-c1-main.csv, assembly.json and the board files."""
    for parent in Path(__file__).resolve().parents:
        for candidate in (parent / "data",):
            if (candidate / "bom-c1-main.csv").is_file():
                return candidate
    raise FileNotFoundError("source data folder not found")


def build_dataset(source: Path | None = None) -> dict:
    source = source or find_source_dir()
    bom = bom_mod.load_all(source)
    return {
        "boards": {
            "c1-main": kicad_pcb.load_c1_board(source / "OSO-BOOK-C1.kicad_pcb", bom),
            "c2-driver": eagle.load_c2_board(source / "OSO-BOOK-C2-02.brd", bom),
        },
        "bom": [{k: v for k, v in line.items() if v is not None} for line in bom],
        "assembly": json.loads((source / "assembly.json").read_text(encoding="utf-8")),
        "costSummary": bom_mod.summarize_cost(bom),
    }


def main(argv: list[str] | None = None) -> int:
    """`python -m open_book_builder.build.dataset_build [output.json]` writes the dataset as JSON."""
    args = sys.argv[1:] if argv is None else argv
    out = Path(args[0]) if args else Path("board-dataset.json")
    out.write_text(json.dumps(build_dataset(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
