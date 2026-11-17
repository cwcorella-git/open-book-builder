"""Footprint height guesses used for the 3D hints (port of footprint_heights.rs)."""
from __future__ import annotations


def height3d_for(fp: str) -> float:
    if fp.startswith("Battery_Holder"):
        return 12.0
    if "SW_SPDT" in fp or fp.startswith("Switch_Slide"):
        return 2.5
    if fp.startswith("TACT_") or "SW_PUSH" in fp:
        return 3.5
    if fp.startswith(("Button_Switch_SMD", "Button_Switch_THT")):
        return 3.5
    if "JST_SH_" in fp:
        return 1.5
    if fp.startswith("Connector_JST"):
        return 4.5
    if "Crystal" in fp:
        return 1.5
    if "RPi_Pico" in fp or "MEM2075" in fp or "OSO-BOOK-C2" in fp:
        return 1.5
    if fp.startswith(("Package_SO", "Package_QFN", "Package_DFN", "Package_TO_SOT")):
        return 1.0
    if any(s in fp for s in ("_0402", "_0603", "_0805", "_1206", "_1210")):
        return 0.6
    return 1.0


def height3d_for_eagle(pkg: str) -> float:
    if "0805" in pkg or "_0603" in pkg:
        return 0.6
    if pkg == "SOD-123" or pkg.startswith("SOT23"):
        return 1.1
    if pkg == "EINK_24PIN":
        return 1.5
    return 1.0
