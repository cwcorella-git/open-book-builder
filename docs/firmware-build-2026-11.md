# Firmware build record, 2026-11-17

A clean compile of libros for the original Pico with community PRs #10 and #11 applied. **This is not hardware validation.** Nothing was flashed and no display was driven.

## Inputs

| Item | Value |
| --- | --- |
| Repository | `https://github.com/joeycastillo/libros`, cloned to `/data/checkouts/libros` |
| Base | `3be5d84` (`main` on 2026-11-17) |
| PR #10 | head `abc2d5fd4de4d4a4cb5e1a5e14884201fcab6b5d` |
| PR #11 | head `a2f91fb871ad04ce62ec3c1193732b39564851a4` |
| Build branch | `obb-pilot` at `5196839bf136b2c3f92f8259b2b9f7393325e11a`, both PRs merged with no conflicts |
| Environment | `pico`: platform `raspberrypi` 1.20.0, board `pico`, Arduino framework |
| PlatformIO | Core 6.2.0, in `/data/checkouts/libros-pio/.venv`, packages in `/data/checkouts/libros-pio/core` |
| Framework | `framework-arduino-mbed` 4.6.0 (this is the mbed-based Arduino core, not arduino-pico) |
| Toolchain | `toolchain-gccarmnoneeabi` 1.90201.191206, `tool-rp2040tools` 1.0.2 |

## Command

```bash
cd /data/checkouts/libros
PLATFORMIO_CORE_DIR=/data/checkouts/libros-pio/core \
systemd-run --user --scope -p MemoryMax=2500M -p MemorySwapMax=0 \
  timeout -k 10 1500 /data/checkouts/libros-pio/.venv/bin/pio run -e pico
```

Result: `SUCCESS`, 61.65 s after the package downloads. About 3.4 GB of RAM was free when it started.

## Outputs (in `.pio/build/pico/`)

| File | Size | SHA-256 |
| --- | ---: | --- |
| `firmware.uf2` | 624,128 bytes | `d2c452ff797be3afa3198fde958d7cb959e096be784734a0ec167562aeb25950` |
| `firmware.bin` | 311,988 bytes | `3629e31fc31f115cc14d674de3e15d3127307b7bcc288bc5130c9687c7d846e8` |

The files are build artifacts and are not committed.

## Things to check before trusting it

- **Implicit declarations in `src/platform/pico/sleep.c`:** `setup_default_uart`, `gpio_set_dormant_irq_enabled` and `gpio_acknowledge_irq` are called without a declaration, because PR #10 removed `#include "pico/stdlib.h"` and the file includes no other header that declares them. Checked 2026-11-17: all three are declared in the framework's own headers (`hardware/gpio.h` lines 396 and 405, `pico/stdlib.h` line 84) and all three are present in the linked ELF. The calls are real: `OpenBookDevice::sleep()` calls `sleep_run_from_rosc()` and `sleep_goto_dormant_until_pin(12, true, false)`. On this 32-bit ARM core an undeclared call with these argument types behaves as the declared one, so this is a warning and not a known fault. The clean fix is to include `hardware/gpio.h` and the header that declares `setup_default_uart` in `sleep.c`. Sleep and wake have still never run on hardware.
- **The PlatformIO size summary is wrong, the file sizes are right.** PlatformIO printed `Flash: 4586 bytes (0.2%)`. `arm-none-eabi-size` on the ELF reports 311,344 bytes of code and 45,508 bytes of bss, which matches the 311,988 byte `firmware.bin`. Use the ELF numbers.
- Other warnings are sign-compare notes in the Adafruit EPD and GFX libraries and register-macro notes inside the framework.
- The display driver (IL0398 or SSD1683) is chosen at runtime from the busy-pin polarity, per PR #11's description. That is source reading. No panel has confirmed it.
- Dependencies were whatever PlatformIO resolved on 2026-11-17 (Adafruit SPIFlash 3.8.0, Adafruit MCP23008, Adafruit EPD and GFX). They are not pinned in `platformio.ini`.
- The two PRs were unmerged on 2026-11-15. Re-check before relying on this record.

## What would make it a validated build

A pilot reader: flash this UF2, put `babel.bin` on the card, boot, confirm text renders on the GDEY042T81, check every button, microSD reading, sleep and wake, USB and battery power. See the Assembly steps, which stay marked Untested until then.
