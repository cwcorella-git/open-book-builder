# GDEY042T81 and the C2 driver: values check

Prepared 2026-11-17 as desk research. **Nothing here validates a build.** It compares Good Display's reference circuit with the published C2-03 design and records what the public reports say. Whether the C2 module drives this panel properly is untested until a pilot reader exists.

## Sources

- Good Display, *GDEY042T81 Product Specifications*, revision 1.0, dated 2023-04-03, 40 pages, section 12 "Reference Circuit" on page 31. This is the copy hosted by Seeed (`files.seeedstudio.com/wiki/Other_Display/42-epaper/GDEY042T81.pdf`). The circuit is a drawing, so it was read from a rendered image. A newer revision on Good Display's own site was not checked.
- The C2-03 schematic and board: `reference/the-open-book/upstream/OSO-BOOK-C2/OSO-BOOK-C2-03.sch` and `.brd` (pinned commit `6bb483f`). Its BOM lists R1 0.47 Ω, L1 10 µH, nine 1 µF and one 4.7 µF capacitors, three MBR0530 diodes and an IRLML0100 MOSFET.
- The-Open-Book issue #77 (read in full through the GitHub API), libros PR #11 and PR #10.

## What matches

- **Topology.** Both are a boost converter plus a negative charge pump. In both, the inductor runs from 3.3 V to a switch node; an N-channel MOSFET has its gate on GDR, its drain on the switch node and its source on RESE; a resistor from RESE to ground senses current; a diode from the switch node feeds PREVGH; and a 4.7 µF capacitor with two diodes forms the negative rail (PREVGL). The C2-03 netlist reproduces this node for node.
- **The panel connector.** The 24-pin FPC signals map the same way: GDR on pin 2, RESE on 3, BS tied to ground, VCI and VDDIO on 3.3 V.
- **Diodes.** MBR0530 in both.
- **Most capacitor values.** The per-rail 1 µF capacitors are present in both. C2-03 uses 50 V parts where the reference shows 25 V; that is more margin, not less.
- **The controller's role.** The spec's pin table calls GDR "N-Channel MOSFET Gate Drive Control" and RESE "Current Sense Input for the Control Loop", which is how C2-03 wires them.

## What differs, and the published board cannot take the reference value as it stands

| Part | Reference | C2-03 | Why it is a problem |
| --- | --- | --- | --- |
| GDR pulldown | R1, 1 MΩ, gate to ground | none | There is no such part and no spare footprint: the board's elements are C1-C10, D1-D3, J1, JP1, L1, Q1, R1 and the two edge blocks. The nearest ground pad to the MOSFET gate pad is 2.66 mm away (C5 pad 1), so a hand-soldered 0402 or 0603 resistor could bridge it, but that is rework on a finished module. A factory cannot add a part the board has no pads for. |
| Inductor L1 | 47 µH, 500 mA | 10 µH, 0805 footprint | The footprint's pads are 1.2 x 1.3 mm at 2.03 mm pitch. I did not look up catalogue parts. A 47 µH inductor rated near 500 mA is generally larger than an 0805 package, so a like-for-like swap is not evident and must be confirmed with the maker's parts library. |

## What differs, and the effect is unknown

| Part | Reference | C2-03 | What is known |
| --- | --- | --- | --- |
| Current-sense resistor | 2.2 Ω | 0.47 Ω (0402, pads 0.6 x 0.6 mm) | An 0402 footprint can physically take a 2.2 Ω chip. How the SSD1683 uses RESE (threshold, timing) is not stated in this specification, so the effect of the change is unknown. |
| MOSFET | Si1308EDL | IRLML0100 (100 V) | Same role. Gate-drive voltage and switching behavior with this controller were not compared. |
| Input capacitor on 3.3 V | 4.7 µF (C4) | 1 µF (C3) | C2-03 has one 4.7 µF capacitor (the charge pump), the reference has two. Effect unknown. |

The reference circuit is a design for the panel's own driver. The older GDEW042T2 (UC8176) ran on the 10 µH / 0.47 Ω values in C2-02 and C2-03; I did not find a reference circuit for that panel to compare, so I cannot say the inductor and resistor values were ever the same as its reference.

## What the public reports establish

- **The creator, 2023-11-21:** "there might be a couple of component swaps required to get the GDEY version working. In particular their spec shows a higher value inductor, a pulldown on one signal line and (maybe?) a different value for the current sense resistor. All the footprints to support this are present on the board; however, I had not published the new values." He has one assembled with the GDEY and had no driver code at the time. **The published files do not show those footprints**: there is no pulldown element and L1 is the 0805. No tested value set was ever published.
- **A commenter, 2023-11-24:** at least in his tests the two panels are "100% hardware compatible and you can just swap one for the other". It is a general statement from his own ESP32 work, not a test on a C2 module, and it is about swapping the panels GDEQ042T81 and GDEY042T81, not about these component values.
- **A builder, May 2024:** got the panel working "with fantastic results" using Waveshare's Pico example code. The comment does not say the panel was on a C2 module rather than on Waveshare's own board.
- **libros PR #11 (2025-12-23):** adds runtime selection between the IL0398 and SSD1683 drivers by reading the busy pin after reset. The description says part of the code was written with Claude Code and does not say it was tested on hardware, on the C2 module or otherwise. It was unmerged when checked.

So there is no evidence either way that the published C2 values drive the GDEY042T81 properly, and no evidence that anyone ran this exact combination.

## What this means for the first ten (a recommendation, not a ruling)

1. **Treat the pilot as the test.** The first assembled C2 with a GDEY042T81 settles the question.
2. **Plan a multimeter and a way to look at the rails.** You have none. C2-03 has no test points, but each panel rail (PREVGH, PREVGL, VCOM, VSH, VSL, VGH, VGL) has its own 1 µF capacitor (C1, C2, C5-C9), so those capacitor pads are the places to put a probe. Measuring them on the pilot is the cheapest evidence. Which voltages to expect is not in this specification's reference circuit and is not checked here.
3. **Ask the module maker two questions in the quote, without assuming the answers:** can they populate R1 as 2.2 Ω in the 0402 footprint (likely a simple BOM change), and do they stock a 47 µH inductor that fits the 0805 pads?
4. **A pulldown needs a board change or hand rework.** Under the "existing revisions first" ruling, a new C2 revision is out of scope unless the pilot shows the existing board unsuitable. A bodged resistor on the pilot module is a reasonable experiment if the first unit misbehaves.
5. Keep the display marked **unvalidated** in the app until a pilot works.

## Not checked

The SSD1683 datasheet; a newer GDEY042T81 specification; Good Display's reference circuit for the GDEW042T2; any manufacturer part catalogue; the sense-resistor power rating at the peak current; the copper layout around Q1 beyond the pad distance above.
