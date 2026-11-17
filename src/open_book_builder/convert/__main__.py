"""Command line: python -m open_book_builder.convert <file or folder> -o <folder>."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import convert


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="open_book_builder.convert", description=__doc__)
    parser.add_argument("source", type=Path, help="A Markdown work, or a folder of them.")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Folder for the reader files.")
    args = parser.parse_args(argv)
    sources = sorted(args.source.glob("*.md")) if args.source.is_dir() else [args.source]
    if not sources:
        print("No .md files found.", file=sys.stderr)
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    failed = 0
    for path in sources:
        result = convert(path.read_bytes())
        for item in result.report.items:
            print(f"{path.name}: {item}")
        if result.data is None:
            failed += 1
            print(f"{path.name}: Not written.")
            continue
        if path.stem != result.header.id:
            print(f"{path.name}: Note: the file name differs from the id '{result.header.id}'. The output uses the id.")
        (args.output / result.filename).write_bytes(result.data)
        print(f"{path.name}: Wrote {result.filename}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
