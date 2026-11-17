# C1 factory assembly package

Prepared 2026-11-17 from `data/OSO-BOOK-C1.kicad_pcb`. It exists because the upstream C1-05 fabrication zip holds Gerbers and drill files only. A factory needs a placement file and an assembly BOM as well, and the repository had neither. Nothing here has been sent to a factory, quoted or ordered.

Regenerate both files with `uv run python scripts/c1_assembly_package.py`.

## Files

- `c1-assembly-package/c1-placement.csv`: 27 parts with designator, footprint, X, Y, rotation, side and how each is expected to be fitted.
- `c1-assembly-package/c1-assembly-bom.csv`: 15 part lines, plus the retainer clip and the display, which are not on the board file. Each line shows its Digi-Key and LCSC numbers where recorded, and a Gap column where they are not.

## Where the data comes from

The positions come from the C1 board source in `data/`. That file is labelled C1-06 on its back silkscreen, and the order package is the C1-05 zip. The comparison recorded in `data/revisions.json` found the outline, the four mounting holes and every drill diameter and count identical, and 159 pad checks within 0.02 mm of the Gerber copper. One difference was found: the 43 Pico SMD pads sit 0.9 mm further out in the C1-05 Gerbers than in the source (`tests/test_gerber_accuracy.py` pins this). The Pico's placement origin and rotation are unaffected, but the pad geometry a factory builds is the Gerber's. Copper traces and silkscreen were not compared.

## What a factory can place

| Fit | Parts | Notes |
| --- | --- | --- |
| SMD, a factory can place it | B1, B2 (side buttons), C1-C3, J1-J3 (optional), Q1, Q2, R1-R4 (R1, R2 optional), SW1, U4 | 16 parts, all on the bottom |
| Large or mechanical | BT1 (battery holder), U1 (Pico), U3 (microSD socket) | Ask whether the factory places these |
| Through-hole | B3-B9 (front buttons) | 7 parts, on the top |
| Module | U2 (C2 driver) | Soldered on by its castellated edge: hand work |

Open solder jumpers JP1 and JP2 are on the board file with no part, so they are left out. The retainer clip (1022C) and the display are not on the board file and are fitted by hand.

## What is not settled

- **No LCSC numbers** are recorded for any C1 part, and none was guessed. JLCPCB-style assembly needs them.
- **Digi-Key numbers** are missing for the Pico (SC0915) and the C2 module.
- **X and Y are footprint origins, not centers.** Factories ask for the part center. Large footprints such as the Pico and the microSD socket can be off by several millimetres.
- **Rotation** is KiCad's. Factories often correct rotation per part from their own library. Check the preview before approving.
- Y is flipped to the usual y-up convention. Confirm the origin the factory expects.
- **Two-sided assembly:** SMD parts are on the bottom and the through-hole buttons are on the top.

## Quote requests

The request texts, the three assembly routes and a comparison table are in [quote-requests.md](quote-requests.md). The Checklist tab keeps the matching items open until a quote exists.
