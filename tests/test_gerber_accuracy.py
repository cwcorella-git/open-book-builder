"""Check the board view's pad positions against the flashes in the C1-05 order Gerbers.

This is what makes "accurate" measurable. The Gerbers are what the PCB maker builds from; the viewer
reads the C1-06-labelled KiCad source. They agree on every pad except the 43 Pico SMD pads, which sit
0.9 mm further out in the Gerbers (in x for pads 1-40, in y for the debug pads 41-43).
"""
import math
import re
import zipfile
from pathlib import Path

import pytest

from open_book_builder.build.dataset_build import build_dataset

ZIP = (Path(__file__).parents[1] / "reference" / "the-open-book" / "upstream" / "Fabrication Files"
       / "Open Book Main Board" / "OSO-BOOK-C1-05-rounded.zip")
pytestmark = pytest.mark.skipif(not ZIP.is_file(), reason="C1-05 fabrication zip not in reference/")

TOLERANCE = 0.02  # mm


def flashes(layer: str) -> list[tuple[float, float]]:
    with zipfile.ZipFile(ZIP) as z:
        name = next(n for n in z.namelist() if n.endswith(f"-{layer}.gbr"))
        text = z.read(name).decode()
    return [(int(m.group(1)) / 1e6, -int(m.group(2)) / 1e6)
            for line in text.splitlines() if (m := re.match(r"X(-?\d+)Y(-?\d+)D03\*", line))]


def pad_points(comp: dict, pad: dict) -> tuple[float, float]:
    th = math.radians(-comp["rotation"])
    return (comp["x"] + pad["x"] * math.cos(th) - pad["y"] * math.sin(th),
            comp["y"] + pad["x"] * math.sin(th) + pad["y"] * math.cos(th))


def near(point, candidates, dx=0.0, dy=0.0):
    return any(abs(point[0] + dx - q[0]) < TOLERANCE and abs(point[1] + dy - q[1]) < TOLERANCE for q in candidates)


def test_every_pad_but_the_pico_matches_the_gerber_copper():
    layers = {"top": flashes("F_Cu"), "bottom": flashes("B_Cu")}
    board = build_dataset()["boards"]["c1-main"]
    checked, missed = 0, []
    for comp in board["components"]:
        for pad in comp["pads"]:
            if comp["ref"] == "U1" and not pad["throughHole"] and pad["number"].isdigit():
                continue  # the Pico SMD pads are checked separately below
            if pad["throughHole"] and not pad["number"]:
                continue  # the Pico's non-plated mounting holes have no copper
            sides = ["top", "bottom"] if pad["throughHole"] else [comp["side"]]
            for side in sides:
                checked += 1
                if not near(pad_points(comp, pad), layers[side]):
                    missed.append((comp["ref"], pad["number"], side))
    assert checked > 150
    assert missed == []


def test_pico_pads_sit_0_9_mm_further_out_in_the_gerbers():
    bottom = flashes("B_Cu")
    board = build_dataset()["boards"]["c1-main"]
    u1 = next(c for c in board["components"] if c["ref"] == "U1")
    pads = [p for p in u1["pads"] if not p["throughHole"] and p["number"].isdigit()]
    assert len(pads) == 43
    for pad in pads:
        x, y = pad_points(u1, pad)
        if int(pad["number"]) <= 40:
            assert near((x, y), bottom, dx=0.9 if x > u1["x"] else -0.9), pad["number"]
        else:  # debug pads on the bottom edge, 1.7 x 3.5 mm
            assert pad["size"] == [1.7, 3.5]
            assert near((x, y), bottom, dy=0.9), pad["number"]


C2_ZIP = (Path(__file__).parents[1] / "reference" / "the-open-book" / "upstream" / "Fabrication Files"
          / "Castellated E-Paper Driver" / "OSO-BOOK-C2-02 (PCBWay)" / "OSO-BOOK-C2-02_2022-07-19.zip")


@pytest.mark.skipif(not C2_ZIP.is_file(), reason="C2-02 fabrication zip not in reference/")
def test_c2_pads_match_the_c2_02_gerber_copper():
    """The viewer draws y down, EAGLE and the Gerbers are y up, so Gerber y is board height minus view y."""
    with zipfile.ZipFile(C2_ZIP) as z:
        text = z.read("GerberFiles/copper_bottom.gbr").decode()
    scale = 10 ** int(re.search(r"%FSLAX\d(\d)Y", text).group(1))
    flashed = [(int(m.group(1)) / scale, int(m.group(2)) / scale)
               for line in text.splitlines() if (m := re.match(r"X(-?\d+)Y(-?\d+)D03\*", line))]
    board = build_dataset()["boards"]["c2-driver"]
    height = board["outline"]["heightMm"]
    checked, missed = 0, []
    for comp in board["components"]:
        for pad in comp["pads"]:
            if pad["throughHole"]:
                continue
            x, y = pad_points(comp, pad)
            checked += 1
            if not near((x, height - y), flashed):
                missed.append((comp["ref"], pad["number"]))
    assert checked == 59
    assert missed == []
