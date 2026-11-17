#!/usr/bin/env python3
"""Copy converted works and the font file onto a mounted Open Book microSD card (Linux).

By default this only prints what it would do. Pass --write to copy. It never formats a card:
format it as FAT32 with your disk tool first. Standard library only.

  prepare_card.py /media/you/CARD --works out/ --babel babel.bin           (dry run)
  prepare_card.py /media/you/CARD --works out/ --babel babel.bin --write
  prepare_card.py /media/you/CARD --works packages/ --select ids.txt --write
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import stat
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

NAME_LIMIT = 127  # the reader keeps file names in char[128]
MARGIN = 4 * 1024 * 1024  # free space kept beyond the copy
KNOWN = {"babel.bin", "_LIBRARY", "_LIBBACK", "_LIBTEMP", "_STATE", "_STATE.tmp"}
KNOWN_SUFFIX = (".txt", ".pag", ".obp")
IGNORED = {"System Volume Information"}


@dataclass
class Result:
    problems: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def parse_mountinfo(text: str) -> dict[str, str]:
    """{mount point: source device} from the text of /proc/self/mountinfo."""
    mounts = {}
    for line in text.splitlines():
        parts = line.split()
        if "-" not in parts:
            continue
        dash = parts.index("-")
        mounts[parts[4].replace("\\040", " ")] = parts[dash + 2]
    return mounts


def block_name(device: str) -> str:
    """The whole-disk name for a partition path: /dev/sdb1 -> sdb, /dev/mmcblk0p1 -> mmcblk0."""
    name = Path(device).name
    match = re.match(r"^(mmcblk\d+|nvme\d+n\d+)p\d+$", name) or re.match(r"^([a-z]+)\d+$", name)
    return match.group(1) if match else name


def check_card(card: Path, mountinfo: str, sys_root: Path = Path("/sys"), allow_fixed: bool = False) -> list[str]:
    """Reasons to refuse this path as a card. An empty list means it looks like a removable card."""
    problems = []
    try:
        mode = card.stat().st_mode
    except OSError:
        return [f"{card} does not exist. Mount the card and pass its folder."]
    if stat.S_ISBLK(mode):
        return [f"{card} is a device. Mount the card first, then pass the folder it was mounted on."]
    if not card.is_dir():
        return [f"{card} is not a folder."]
    mounts = parse_mountinfo(mountinfo)
    real = str(card.resolve())
    if real not in mounts:
        return [f"{card} is not the top of a mounted card. Pass the mount folder itself, for example /media/you/CARD."]
    if real == "/":
        return ["That is the root of this computer's disk."]
    device = mounts[real]
    if not device.startswith("/dev/"):
        return [f"{real} is not backed by a disk ({device})."]
    flag = sys_root / "block" / block_name(device) / "removable"
    try:
        removable = flag.read_text().strip() == "1"
    except OSError:
        removable = None
    if not removable and not allow_fixed:
        why = "cannot be checked" if removable is None else "is not marked removable"
        problems.append(
            f"The disk behind {real} ({device}) {why}. Built-in card readers often look fixed. "
            "If this is your card, run again with --allow-fixed."
        )
    return problems


def unrecognized(card: Path) -> list[str]:
    """Names in the card root that the reader does not use."""
    odd = []
    for entry in sorted(card.iterdir()):
        name = entry.name
        if name in IGNORED or name.startswith(".") or name in KNOWN:
            continue
        if entry.is_file() and name.endswith(KNOWN_SUFFIX):
            continue
        odd.append(name)
    return odd


def load_works(source: Path, select: set[str] | None) -> tuple[dict[str, bytes], list[str]]:
    """{file name: bytes} from a folder of .txt files and/or zip packages. Returns (works, problems)."""
    works: dict[str, bytes] = {}
    problems = []

    def add(name: str, data: bytes) -> None:
        if select is not None and name[:-4] not in select:
            return
        if name in works and works[name] != data:
            problems.append(f"Two different files are named {name}.")
        works[name] = data

    paths = [source] if source.is_file() else sorted(source.iterdir())
    for path in paths:
        if path.name.endswith(".reading.txt"):
            continue  # the plain reading copy from the converter is not a reader file
        if path.suffix == ".txt":
            add(path.name, path.read_bytes())
        elif path.suffix == ".zip":
            with zipfile.ZipFile(path) as z:
                for member in z.namelist():
                    if member.endswith(".txt") and not member.endswith(".reading.txt") and "/" not in member and not member.startswith("."):
                        add(member, z.read(member))
    if select is not None:
        missing = sorted(select - {n[:-4] for n in works})
        problems += [f"The selection asks for '{m}' but no such work was found." for m in missing]
    return works, problems


def prepare(card: Path, files: dict[str, bytes], write: bool, free_bytes: int | None = None) -> Result:
    """Plan (and with write=True perform) the copy. `files` maps card file names to their bytes."""
    result = Result()
    for name in files:
        if "/" in name or name.startswith(".") or len(name.encode()) > NAME_LIMIT - 1:
            result.problems.append(f"The name '{name}' is not allowed (no folders, no leading dot, under {NAME_LIMIT} bytes).")
    odd = unrecognized(card)
    if odd:
        result.problems.append(
            "The card holds files the reader does not use: " + ", ".join(odd[:8]) + ". "
            "Move them off the card or use a card that is only for the reader."
        )
    todo = []
    for name, data in sorted(files.items()):
        target = card / name
        if target.exists() and target.read_bytes() == data:
            result.notes.append(f"{name} is already on the card.")
            continue
        todo.append((name, data, target.exists()))
    need = sum(len(d) for _, d, _ in todo) + MARGIN
    free = shutil.disk_usage(card).free if free_bytes is None else free_bytes
    if todo and free < need:
        result.problems.append(f"The card has {free // 1024} KiB free and the copy needs {need // 1024} KiB.")
    for name, data, existed in todo:
        result.actions.append(f"{'Replace' if existed else 'Copy'} {name} ({len(data)} bytes).")
        if existed and name.endswith(".txt"):
            stem = name[:-4]
            if (card / f"{stem}.pag").exists():
                result.actions.append(f"Delete {stem}.pag (the page map belongs to the old text).")
            if (card / f"{stem}.obp").exists():
                result.notes.append(
                    f"{stem}.obp was kept. The saved page may sit in the wrong place after the edit (open decision)."
                )
    if not write or result.problems:
        return result
    for name, data, existed in todo:
        target = card / name
        if existed and name.endswith(".txt"):
            (card / f"{name[:-4]}.pag").unlink(missing_ok=True)
        target.write_bytes(data)
    os.sync()
    for name, data, _ in todo:
        if hashlib.sha256((card / name).read_bytes()).digest() != hashlib.sha256(data).digest():
            result.problems.append(f"{name} was copied but reads back differently. Replace the card or try again.")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("card", type=Path, help="The folder the card is mounted on.")
    parser.add_argument("--works", type=Path, required=True, help="A folder of .txt files and zip packages, or one file.")
    parser.add_argument("--babel", type=Path, help="The font file, copied as babel.bin.")
    parser.add_argument("--select", type=Path, help="A text file listing work ids to copy, one per line.")
    parser.add_argument("--write", action="store_true", help="Copy for real. Without it, only print the plan.")
    parser.add_argument("--allow-fixed", action="store_true", help="Accept a disk that is not marked removable.")
    args = parser.parse_args(argv)

    problems = check_card(args.card, Path("/proc/self/mountinfo").read_text(), allow_fixed=args.allow_fixed)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    select = None
    if args.select:
        select = {l.strip() for l in args.select.read_text().splitlines() if l.strip() and not l.startswith("#")}
    files, problems = load_works(args.works, select)
    if args.babel:
        if not args.babel.is_file():
            problems.append(f"{args.babel} is not a file.")
        else:
            files["babel.bin"] = args.babel.read_bytes()
    if not files and not problems:
        problems.append("There is nothing to copy.")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    result = prepare(args.card, files, args.write)
    for line in result.actions + result.notes:
        print(line)
    if result.problems:
        print("\n".join(result.problems), file=sys.stderr)
        return 2
    print("Done." if args.write else "That was a dry run. Nothing was copied. Add --write to copy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
