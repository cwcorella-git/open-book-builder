#!/usr/bin/env python3
"""Build babel.bin, the reader's font and character table, from GNU Unifont and the Unicode data files.

  build_babel.py --hex unifont_all-15.1.05.hex --ucd DIR -o babel.bin
      DIR holds LineBreak.txt, BidiMirroring.txt and UnicodeData.txt for the Unicode version of the Python running this
      (see unicodedata.unidata_version, printed at the end). Output is 2 MiB, the size of the reader's flash chip.

The layout is read from the libros firmware (src/components/language/BabelDevice.cpp and BabelMacros.h) and checked
against the original babel.bin from the Open Book project. Little endian throughout.

  offset 0     u16 reserved, must be 0
  offset 2     u16 version, must be 1
  offset 4     u8  glyph width (8), offset 5 u8 glyph height (16), offset 6 u16 flags (0)
  offset 8     u32 start of glyph data
  offset 12    u16 first code point, offset 14 u16 last code point (0, 0xFFFF)
  offset 16    u32 start of the lookup table (256)
  offset 148   u32 start of the extras table (152)
  offset 152   extras entries of two u32: (start << 8 | type), (length << 8); a zero entry ends the list.
               type 1 upper case, 2 lower case, 3 title case, 4 mirroring: each a sorted array of u32
               (key | value << 16). The original file also has a type 64 entry that the firmware ignores;
               this builder does not write it.
  lookup table 6 bytes per code point 0..0xFFFF: u32 info, u16 extended info. Unlisted code points are zero.
      info: bits 0-21 glyph location in the file, 22-26 glyph width in pixels (8 or 16), 27 non-spacing mark,
            28 strong right-to-left, 29 strong left-to-right (both set: mirrored in right-to-left text),
            30 control character, 31 line break opportunity
      extended: bits 0-4 general category (1 Lu ... 30 Cn), 5 6 7 has an upper, lower, title case mapping,
            8-11 bidi class (1 L ... 15), 12 has a mirroring mapping, 13 whitespace
  glyph data   16 bytes for an 8 pixel wide glyph, 32 bytes for a 16 pixel wide one, in code point order. The bytes
               are the hex string of Unifont's .hex file, row by row, with no change.

What the source does not settle (and this builder had to infer by comparing with the original file) is written
next to each rule below.
"""
from __future__ import annotations

import argparse
import struct
import sys
import unicodedata
from pathlib import Path

SIZE = 2 * 1024 * 1024
LUT = 256
CATEGORIES = ["Lu", "Ll", "Lt", "Lm", "Lo", "Mn", "Mc", "Me", "Nd", "Nl", "No", "Pc", "Pd", "Ps", "Pe", "Pi", "Pf",
              "Po", "Sm", "Sc", "Sk", "So", "Zs", "Zl", "Zp", "Cc", "Cf", "Cs", "Co", "Cn"]
BIDI = ["L", "R", "AL", "EN", "ES", "ET", "AN", "CS", "NSM", "BN", "B", "S", "WS", "ON"]
# Unicode line breaking classes after which a line may break (inferred: they match the original file exactly)
BREAK_AFTER = {"B2", "BA", "HY", "ID", "SP", "SY"}


def read_hex(path: Path) -> dict[int, bytes]:
    glyphs = {}
    for line in path.read_text().splitlines():
        cp, _, bits = line.strip().partition(":")
        if cp and int(cp, 16) <= 0xFFFF:
            glyphs[int(cp, 16)] = bytes.fromhex(bits)
    return glyphs


def read_ranges(path: Path) -> dict[int, str]:
    out = {}
    for line in path.read_text().splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        rng, _, value = line.partition(";")
        a, _, b = rng.strip().partition("..")
        for cp in range(int(a, 16), int(b or a, 16) + 1):
            if cp <= 0xFFFF:
                out[cp] = value.strip()
    return out


def read_mirroring(path: Path) -> dict[int, int]:
    out = {}
    for line in path.read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            a, _, b = line.partition(";")
            if int(a, 16) <= 0xFFFF and int(b, 16) <= 0xFFFF:
                out[int(a, 16)] = int(b, 16)
    return out


def is_control(cp: int, category: str) -> bool:
    """Cc and Cf are all control characters in the original, and so are U+E000 and U+F8FF (inferred)."""
    return category in ("Cc", "Cf") or cp in (0xE000, 0xF8FF)


def right_to_left_block(cp: int) -> bool:
    """Combining marks (bidi class NSM) in these blocks count as strong right to left (inferred: this matches all
    221 in the original)."""
    return 0x0590 <= cp <= 0x08FF or 0xFB1D <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF


def read_case(path: Path) -> dict[str, dict[int, int]]:
    """Simple upper, lower and title case mappings from UnicodeData.txt (fields 12 to 14). A character whose title
    case is itself is still listed, as in the original."""
    maps = {"upper": {}, "lower": {}, "title": {}}
    for line in path.read_text().splitlines():
        f = line.split(";")
        cp = int(f[0], 16)
        if cp > 0xFFFF or len(f) < 15:
            continue
        for index, name in ((12, "upper"), (13, "lower"), (14, "title")):
            if f[index] and int(f[index], 16) <= 0xFFFF:
                maps[name][cp] = int(f[index], 16)
    return maps


def ucd_version(ucd: Path) -> str:
    """The Unicode version named in the first line of LineBreak.txt, such as 15.0.0."""
    first = (ucd / "LineBreak.txt").read_text().splitlines()[0]
    return first.removeprefix("# LineBreak-").removesuffix(".txt").strip()


def build(hex_path: Path, ucd: Path, allow_version_mismatch: bool = False) -> bytes:
    version = ucd_version(ucd)
    if version != unicodedata.unidata_version and not allow_version_mismatch:
        raise ValueError(
            f"The data files are Unicode {version} but this Python knows Unicode {unicodedata.unidata_version}, which "
            "supplies the category and direction of each character. Use matching files, or another Python."
        )
    glyphs = read_hex(hex_path)
    line_break = read_ranges(ucd / "LineBreak.txt")
    mirror = read_mirroring(ucd / "BidiMirroring.txt")
    case = read_case(ucd / "UnicodeData.txt")

    out = bytearray(b"\xff" * SIZE)
    table = bytearray(0x10000 * 6)
    data_start = LUT + len(table)
    position = data_start
    # Unassigned (Cn) and private use (Co) code points are left out, as in the original file (inferred).
    glyphs = {cp: g for cp, g in glyphs.items()
              if unicodedata.category(chr(cp)) not in ("Cn", "Co") or cp in (0xE000, 0xF8FF)}
    for cp in sorted(glyphs):
        bitmap = glyphs[cp]
        if len(bitmap) not in (16, 32):
            raise ValueError(f"U+{cp:04X} has a glyph of {len(bitmap)} bytes")
        width = 8 if len(bitmap) == 16 else 16
        ch = chr(cp)
        category = unicodedata.category(ch)
        bidi = unicodedata.bidirectional(ch)
        mirrored = unicodedata.mirrored(ch) == 1  # includes 120 characters that have no mirrored glyph to swap to
        info = position | (width << 22)
        if category in ("Mn", "Mc", "Me"):
            info |= 1 << 27
        if mirrored:
            info |= 3 << 28
        elif bidi in ("R", "AL", "RLE", "RLI", "RLO") or (bidi == "NSM" and right_to_left_block(cp)):
            info |= 1 << 28
        elif bidi in ("L", "LRE", "LRI", "LRO"):
            info |= 1 << 29
        if is_control(cp, category):
            info |= 1 << 30
        if line_break.get(cp, "XX") in BREAK_AFTER:
            info |= 1 << 31
        extended = CATEGORIES.index(category) + 1
        for bit, which in ((0x20, "upper"), (0x40, "lower"), (0x80, "title")):
            if cp in case[which]:
                extended |= bit
        extended |= (BIDI.index(bidi) + 1 if bidi in BIDI else 15) << 8
        if cp in mirror:
            extended |= 0x1000
        if ch.isspace() and not 0x1C <= cp <= 0x1F:  # tab to carriage return count, the four separators do not
            extended |= 0x2000
        struct.pack_into("<IH", table, cp * 6, info, extended)
        out[position : position + len(bitmap)] = bitmap
        position += len(bitmap)

    extras = []
    blobs = []
    for kind, pairs in ((1, [(cp, v) for cp, v in case["upper"].items() if cp in glyphs]),
                        (2, [(cp, v) for cp, v in case["lower"].items() if cp in glyphs]),
                        (3, [(cp, v) for cp, v in case["title"].items() if cp in glyphs]),
                        (4, [(cp, v) for cp, v in mirror.items() if cp in glyphs])):
        pairs = sorted(pairs)
        blob = b"".join(struct.pack("<I", k | (v << 16)) for k, v in pairs)
        extras.append((kind, len(blob)))
        blobs.append(blob)
    start = position
    entries = bytearray()
    for (kind, length), blob in zip(extras, blobs):
        entries += struct.pack("<II", (start << 8) | kind, length << 8)
        out[start : start + len(blob)] = blob
        start += len(blob)
    entries += struct.pack("<II", 0, 0)
    if start > SIZE:
        raise ValueError("The tables do not fit in 2 MiB.")

    struct.pack_into("<HHBBHI", out, 0, 0, 1, 8, 16, 0, data_start)
    struct.pack_into("<HHI", out, 12, 0, 0xFFFF, LUT)
    struct.pack_into("<I", out, 148, 152)
    out[16 + 4 : 148] = bytes(148 - 20)
    out[152 : 152 + len(entries)] = entries
    out[LUT : LUT + len(table)] = table
    return bytes(out)


class BabelReader:
    """The firmware's BabelDevice reading a babel.bin, step for step (begin, fetch_glyph_*, mapping search)."""

    def __init__(self, data: bytes):
        self.d = data
        u16 = lambda o: struct.unpack_from("<H", data, o)[0]
        u32 = lambda o: struct.unpack_from("<I", data, o)[0]
        if u16(0) != 0 or u16(2) != 1:
            raise ValueError("Not a version 1 babel file.")
        self.width, self.height = data[4], data[5]
        self.glyphs, self.last, self.lut, self.extras = u32(8), u16(14), u32(16), u32(148)
        self.maps: dict[int, tuple[int, int]] = {}
        pos = self.extras
        while True:
            loc, length = u32(pos), u32(pos + 4)
            pos += 8
            if not loc or pos >= 256:
                break
            self.maps[loc & 0xFF] = (loc >> 8, length >> 8)

    def info(self, cp: int) -> int:
        return struct.unpack_from("<I", self.d, self.lut + cp * 6)[0]

    def extended(self, cp: int) -> int:
        return struct.unpack_from("<H", self.d, self.lut + cp * 6 + 4)[0]

    def glyph(self, cp: int) -> bytes:
        info = self.info(cp)
        loc, width = info & 0x3FFFFF, (info >> 22) & 0x1F
        return self.d[loc : loc + (32 if width > 8 else 16)]

    def mapping(self, kind: int) -> dict[int, int]:
        start, length = self.maps[kind]
        return {w & 0xFFFF: w >> 16 for w in struct.unpack_from(f"<{length // 4}I", self.d, start)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hex", type=Path, required=True, help="Unifont .hex file (BMP glyphs are used).")
    parser.add_argument("--ucd", type=Path, required=True, help="Folder with LineBreak.txt, BidiMirroring.txt and UnicodeData.txt.")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--allow-version-mismatch", action="store_true",
                        help="Build even when the data files and this Python disagree on the Unicode version.")
    args = parser.parse_args(argv)
    try:
        data = build(args.hex, args.ucd, args.allow_version_mismatch)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    args.output.write_bytes(data)
    print(f"Wrote {args.output} ({len(data)} bytes). Python's Unicode data is version {unicodedata.unidata_version}; "
          f"the data files in {args.ucd} must be the same version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
