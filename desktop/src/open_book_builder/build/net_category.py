"""Net-name classification (port of net_category.rs)."""
from __future__ import annotations

POWER_PREFIX = ("vcc", "vdd", "+3v3", "+3.3v", "+5v", "+batt", "vbus", "vbat", "vsys", "vpp", "vee", "vdda")
GROUND_PREFIX = ("gnd", "vss", "agnd", "dgnd", "pgnd")
SPI_PARTS = ("sclk", "_sck", "/sck", "miso", "mosi", "cipo", "copi", "display_cs", "display_dc", "display_mosi",
             "display_sck", "sd_cs", "babel_cs", "eink_cs", "eink_dc", "eink_sck", "eink_mosi")
I2C_PARTS = ("sda", "scl", "i2c")
DEBUG_PARTS = ("swdio", "swclk", "jtag", "uart")
ANALOG_PARTS = ("analog", "adc", "vref")
GPIO_PARTS = ("btn_", "button", "led", "gp26", "gp27", "sd_cd", "display_busy", "display_reset", "eink_busy",
              "eink_rst", "/en", "~{en")

PRIORITY = ["power", "ground", "spi", "i2c", "debug", "analog", "gpio", "other"]


def classify_net_name(name: str) -> str:
    n = name.lower()
    if n.startswith(POWER_PREFIX) or "+3.3vp" in n or "+3v3" in n:
        return "power"
    if n.startswith(GROUND_PREFIX):
        return "ground"
    if n == "sck" or any(p in n for p in SPI_PARTS):
        return "spi"
    if any(p in n for p in I2C_PARTS):
        return "i2c"
    if any(p in n for p in DEBUG_PARTS) or (n.endswith("reset") and "display" not in n):
        return "debug"
    if any(p in n for p in ANALOG_PARTS):
        return "analog"
    if any(p in n for p in GPIO_PARTS):
        return "gpio"
    return "other"


def pick_dominant(pads: list[dict]) -> str | None:
    counts = [0] * 8
    any_net = False
    for pad in pads:
        name = pad.get("netName")
        if name is None or name.startswith("unconnected-"):
            continue
        counts[PRIORITY.index(classify_net_name(name))] += 1
        any_net = True
    if not any_net:
        return None
    best_idx, best = 0, 0
    for i, c in enumerate(counts):
        if c > best:
            best, best_idx = c, i
    return PRIORITY[best_idx]
