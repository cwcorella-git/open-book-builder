"""babel.bin builder, against a tiny synthetic Unifont and Unicode data set (the real files are not in the repo)."""
import importlib.util
import sys
import unicodedata
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("build_babel", Path(__file__).parent.parent / "scripts" / "build_babel.py")
bb = importlib.util.module_from_spec(spec)
sys.modules["build_babel"] = bb
spec.loader.exec_module(bb)

GLYPH8 = lambda n: f"{n:02X}" * 16
GLYPH16 = lambda n: f"{n:02X}" * 32

HEX = {
    0x0000: GLYPH8(1), 0x0009: GLYPH8(2), 0x0020: GLYPH8(3), 0x0028: GLYPH8(4), 0x0029: GLYPH8(5),
    0x0041: GLYPH8(6), 0x0061: GLYPH8(7), 0x00AD: GLYPH8(8), 0x0300: GLYPH8(9), 0x05D0: GLYPH8(10),
    0x4E2D: GLYPH16(11), 0x200B: GLYPH8(12), 0x0378: GLYPH8(13), 0xE001: GLYPH8(14), 0xE000: GLYPH8(15),
}


@pytest.fixture(scope="module")
def ucd(tmp_path_factory):
    d = tmp_path_factory.mktemp("ucd")
    (d / "u.hex").write_text("\n".join(f"{cp:04X}:{bits}" for cp, bits in HEX.items()) + "\n")
    (d / "LineBreak.txt").write_text(
        f"# LineBreak-{unicodedata.unidata_version}.txt\n0020;SP\n4E00..9FFF;ID\n200B;ZW\n00AD;BA\n0041;AL\n0061;AL\n"
        "0028;OP\n0029;CP\n0300;CM\n05D0;HL\n0009;BA\n"
    )
    (d / "BidiMirroring.txt").write_text("0028; 0029 # (\n0029; 0028 # )\n")
    (d / "UnicodeData.txt").write_text(
        "0041;LATIN CAPITAL LETTER A;Lu;0;L;;;;;N;;;;0061;\n"
        "0061;LATIN SMALL LETTER A;Ll;0;L;;;;;N;;;0041;;0041\n"
    )
    return d


@pytest.fixture(scope="module")
def built(ucd):
    data = bb.build(ucd / "u.hex", ucd)
    return data, bb.BabelReader(data)


def test_size_and_header(built):
    data, r = built
    assert len(data) == 2 * 1024 * 1024
    assert (r.width, r.height, r.last, r.lut) == (8, 16, 0xFFFF, 256)
    assert r.glyphs == 256 + 0x10000 * 6 and r.extras == 152


def test_unassigned_and_private_use_are_left_out_except_the_two_controls(built):
    _, r = built
    assert r.info(0x0378) == 0 and r.info(0xE001) == 0 and r.info(0x1234) == 0
    assert r.info(0xE000) >> 30 & 1  # U+E000 is kept and counts as a control character


def test_glyphs_round_trip_and_widths(built):
    _, r = built
    for cp, bits in HEX.items():
        if r.info(cp):
            assert r.glyph(cp) == bytes.fromhex(bits), hex(cp)
    assert (r.info(0x41) >> 22) & 31 == 8 and (r.info(0x4E2D) >> 22) & 31 == 16
    assert len(r.glyph(0x4E2D)) == 32 and len(r.glyph(0x41)) == 16


def test_info_flags(built):
    _, r = built
    bit = lambda cp, n: bool(r.info(cp) >> n & 1)
    assert bit(0x41, 29) and not bit(0x41, 28) and not bit(0x41, 31)  # strong left to right, no break after a letter
    assert bit(0x5D0, 28) and not bit(0x5D0, 29)  # Hebrew letter: strong right to left
    assert bit(0x28, 28) and bit(0x28, 29)  # mirrored: both bits
    assert bit(0x300, 27)  # combining mark
    assert bit(0x20, 31) and bit(0x4E2D, 31) and bit(0x9, 31)  # break after space, ideograph, tab
    assert not bit(0x200B, 31)  # a zero width space is not one of the break classes the original sets
    assert bit(0x0, 30) and bit(0xAD, 30) and bit(0x200B, 30)  # Cc and Cf are control characters


def test_extended_info(built):
    _, r = built
    assert r.extended(0x41) & 0x1F == 1 and r.extended(0x41) & 0x40  # Lu, has a lower case mapping
    assert r.extended(0x61) & 0x1F == 2 and r.extended(0x61) & 0xA0 == 0xA0  # Ll, upper and title
    assert (r.extended(0x41) >> 8) & 15 == 1 and (r.extended(0x5D0) >> 8) & 15 == 2  # L, R
    assert r.extended(0x20) & 0x2000 and r.extended(0x9) & 0x2000 and not r.extended(0x41) & 0x2000
    assert r.extended(0x28) & 0x1000 and not r.extended(0x41) & 0x1000


def test_mappings_are_sorted_and_correct(built):
    _, r = built
    assert r.mapping(1) == {0x61: 0x41}
    assert r.mapping(2) == {0x41: 0x61}
    assert r.mapping(3) == {0x61: 0x41}
    assert r.mapping(4) == {0x28: 0x29, 0x29: 0x28}
    start, length = r.maps[1]
    assert start >= r.glyphs and length == 4


def test_output_is_repeatable(built, ucd):
    assert bb.build(ucd / "u.hex", ucd) == built[0]


def test_a_unicode_version_mismatch_is_refused(tmp_path):
    (tmp_path / "LineBreak.txt").write_text("# LineBreak-1.0.0.txt\n")
    (tmp_path / "BidiMirroring.txt").write_text("")
    (tmp_path / "UnicodeData.txt").write_text("")
    (tmp_path / "u.hex").write_text("0041:" + GLYPH8(1) + "\n")
    with pytest.raises(ValueError, match="Unicode 1.0.0"):
        bb.build(tmp_path / "u.hex", tmp_path)
    assert bb.build(tmp_path / "u.hex", tmp_path, allow_version_mismatch=True)


def test_a_glyph_of_the_wrong_size_is_refused(tmp_path):
    (tmp_path / "LineBreak.txt").write_text(f"# LineBreak-{unicodedata.unidata_version}.txt\n")
    (tmp_path / "BidiMirroring.txt").write_text("")
    (tmp_path / "UnicodeData.txt").write_text("")
    (tmp_path / "u.hex").write_text("0041:AABB\n")
    with pytest.raises(ValueError, match="glyph of 2 bytes"):
        bb.build(tmp_path / "u.hex", tmp_path)


def test_reader_rejects_a_file_that_is_not_babel(tmp_path):
    with pytest.raises(ValueError):
        bb.BabelReader(b"\x01\x00" + bytes(300))
