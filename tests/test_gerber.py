"""Unit tests for the Gerber and Excellon reader, on small hand-written files, then on the real order files."""
import math
import zipfile
from pathlib import Path

import pytest

from open_book_builder.build.gerber import evaluate, parse_drill, parse_gerber

FS = "%FSLAX46Y46*%\n%MOMM*%\n"


def bbox(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def test_coordinate_format_and_units():
    layer = parse_gerber(FS + "%ADD10C,1.0*%\nD10*\nX1500000Y-2250000D03*\nM02*\n")
    assert layer.ops == [("flash", "D", 10, 1.5, -2.25)]
    inch = parse_gerber("%FSLAX24Y24*%\n%MOIN*%\n%ADD10C,0.1*%\nD10*\nX10000Y20000D03*\n")
    assert inch.ops[0][3:] == (pytest.approx(25.4), pytest.approx(50.8))
    assert bbox(inch.apertures[10][0][1])[2] == pytest.approx(0.05 * 25.4)


def test_aperture_shapes():
    layer = parse_gerber(FS + "%ADD10R,2.0X1.0*%\n%ADD11O,3.0X1.0*%\n%ADD12C,0.8*%\nD10*\nD11*\nD12*\nX0Y0D03*\n")
    x0, y0, x1, y1 = bbox(layer.apertures[10][0][1])
    assert (x1 - x0, y1 - y0) == (2.0, 1.0)
    x0, y0, x1, y1 = bbox(layer.apertures[11][0][1])
    assert (x1 - x0, y1 - y0) == (pytest.approx(3.0), pytest.approx(1.0))
    assert layer.round_widths == {12: 0.8}


def test_macro_round_rect_and_expressions():
    assert evaluate("$1+$1", [0.25]) == 0.5
    assert evaluate("1.08239X$1", [2.0]) == pytest.approx(2.16478)
    text = (FS + "%AMRoundRect*\n0 comment*\n0 $1 radius*\n4,1,4,$2,$3,$4,$5,$6,$7,$8,$9,$2,$3,0*\n"
            "1,1,$1+$1,$2,$3*\n1,1,$1+$1,$4,$5*\n1,1,$1+$1,$6,$7*\n1,1,$1+$1,$8,$9*%\n"
            "%ADD10RoundRect,0.25X-1.0X-0.5X1.0X-0.5X1.0X0.5X-1.0X0.5X0*%\nD10*\nX0Y0D03*\n")
    layer = parse_gerber(text)
    shapes = layer.apertures[10]
    assert len(shapes) == 5 and all(exposure == 1 for exposure, _ in shapes)
    x0, y0, x1, y1 = bbox([p for _, pts in shapes for p in pts])
    assert (x1 - x0, y1 - y0) == (pytest.approx(2.5), pytest.approx(1.5))  # 2 x 1 body plus 0.25 rounding each side
    assert not layer.unsupported


def test_straight_stroke_and_modal_coordinates():
    layer = parse_gerber(FS + "%ADD10C,0.2*%\nD10*\nX0Y0D02*\nG01X2000000Y0D01*\nY1000000D01*\n")
    assert layer.ops == [("stroke", "D", 0.2, [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0)])]


def test_arcs_go_the_right_way_round():
    ccw = parse_gerber(FS + "%ADD10C,0.1*%\nD10*\nG75*\nX1000000Y0D02*\nG03X0Y1000000I-1000000J0D01*\n")
    cw = parse_gerber(FS + "%ADD10C,0.1*%\nD10*\nG75*\nX1000000Y0D02*\nG02X0Y1000000I-1000000J0D01*\n")
    for layer, expect_midpoint_positive in ((ccw, True), (cw, False)):
        pts = layer.ops[0][3]
        assert pts[0] == (1.0, 0.0) and pts[-1] == pytest.approx((0.0, 1.0))
        assert all(abs(math.hypot(x, y) - 1.0) < 1e-9 for x, y in pts)
        mid = pts[len(pts) // 2]
        # counterclockwise from (1,0) to (0,1) is the short quarter, clockwise is the long three quarters
        assert (mid[0] > 0 and mid[1] > 0) == expect_midpoint_positive


def test_regions_and_polarity():
    text = (FS + "G36*\nX0Y0D02*\nG01X2000000Y0D01*\nX2000000Y2000000D01*\nX0Y2000000D01*\nX0Y0D01*\nG37*\n"
            "%LPC*%\nG36*\nX500000Y500000D02*\nX1500000Y500000D01*\nX1500000Y1500000D01*\nX500000Y500000D01*\nG37*\n")
    layer = parse_gerber(text)
    assert [(op[0], op[1]) for op in layer.ops] == [("region", "D"), ("region", "C")]
    assert layer.ops[0][2][0] == (0.0, 0.0) and len(layer.ops[0][2]) == 5


def test_unsupported_things_are_counted_not_guessed():
    layer = parse_gerber(FS + "%SRX2Y2I1J1*%\n%ADD10C,1.0*%\n")
    assert layer.unsupported == {"SR": 1}


def test_drill_files():
    metric = parse_drill("M48\nMETRIC,TZ,000.000\nT1C1.152\n%\nG90\nT1\nX16510Y27940\nM30\n")
    assert metric == [(16.51, 27.94, 1.152)]
    inch = parse_drill("M48\nINCH\nT1C0.0394\n%\nT1\nX1.0Y-2.0\nM30\n")
    assert inch == [(pytest.approx(25.4), pytest.approx(-50.8), pytest.approx(0.0394 * 25.4))]


# -- the real order files --------------------------------------------------------------------------
FAB = Path(__file__).parents[1] / "data" / "fabrication"
C1 = FAB / "OSO-BOOK-C1-05-rounded.zip"
C2 = FAB / "OSO-BOOK-C2-03.zip"


def read(zp, suffix):
    with zipfile.ZipFile(zp) as z:
        return z.read(next(n for n in z.namelist() if n.endswith(suffix))).decode(errors="ignore")


@pytest.mark.skipif(not C1.is_file(), reason="C1-05 zip not in data/fabrication")
def test_real_c1_layers_parse_fully():
    for suffix in ("-F_Cu.gbr", "-B_Cu.gbr", "-F_Silkscreen.gbr", "-B_Silkscreen.gbr", "-Edge_Cuts.gbr"):
        layer = parse_gerber(read(C1, suffix))
        assert layer.ops and not layer.unsupported, (suffix, layer.unsupported)
    edge = parse_gerber(read(C1, "-Edge_Cuts.gbr"))
    pts = [p for op in edge.ops if op[0] == "stroke" for p in op[3]]
    assert bbox(pts)[0] == pytest.approx(0.0) and bbox(pts)[2] == pytest.approx(85.0)
    assert bbox(pts)[1] == pytest.approx(-115.0) and bbox(pts)[3] == pytest.approx(0.0)  # KiCad Gerber y is the negative of the design's
    drills = parse_drill(read(C1, "-PTH.drl")) + parse_drill(read(C1, "-NPTH.drl"))
    assert len(drills) == 126 + 9


@pytest.mark.skipif(not C2.is_file(), reason="C2-03 zip not in data/fabrication")
def test_real_c2_layers_parse_fully():
    for suffix in ("copper_bottom.gbr", "copper_top.gbr", "silkscreen_bottom.gbr", "profile.gbr"):
        layer = parse_gerber(read(C2, suffix))
        assert not layer.unsupported, (suffix, layer.unsupported)
    bottom = parse_gerber(read(C2, "copper_bottom.gbr"))
    assert any(op[1] == "C" for op in bottom.ops)  # the clear-polarity cut outs around the pours
    assert len(parse_drill(read(C2, ".xln"))) == 40
