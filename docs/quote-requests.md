# Quote requests (drafts)

Prepared 2026-11-17. **Nothing here has been sent.** No maker has been contacted, nothing is quoted or ordered. Square brackets mark things only you can fill in. Every capability statement below is a question, not a claim that the maker offers it.

## What is being quoted

One reader design, ten units: **one pilot, then nine**, and separately **all ten at once**. Hardware is identical across the ten: existing C1 and C2 revisions, original Pico SC0915, no J1-J3 expansion fitted (`docs/hardware-build-review-2026-11-15.md`, rulings of 2026-11-17). Delivery is to the United States. Ask for the same scope at quantity one and at quantity ten, then the follow-on nine, so the two sequences can be compared.

Known gaps to state in every request, so nobody has to guess:
- The C1-05 zip holds Gerbers and drill files only. The placement file and BOM are in `docs/c1-assembly-package/` and are derived, not factory-checked.
- No LCSC numbers are recorded for any C1 part, and the Pico and C2 module have no Digi-Key number recorded here. Do not let a maker substitute a part without telling you.
- The display and the C2 values are unvalidated (`docs/gdey-c2-values-check.md`).

## Request 1: C1 main board, bare PCB (any PCB maker)

> Please quote a bare printed circuit board, delivered to [delivery address], United States.
>
> - Files: `OSO-BOOK-C1-05-rounded.zip` (SHA-256 `a28af22e4787ca4e311a2fb1c486f7d9353da0bae237a103583acbfc15e749bb`), from the Open Book repository, commit `6bb483f`.
> - Board: 85.1 x 115.1 mm, two copper layers, 1.0 mm thick.
> - Finish: please price lead-free HASL and ENIG separately.
> - Quantities: 1, 9 and 10.
>
> Please itemize: fabrication, tooling or setup, shipping, tax or import charges, and lead time for each quantity. Say whether quantity 9 ordered later repeats any setup charge, and what the minimum order is.

## Request 2: C1 assembly (a maker that offers assembly)

> I would like a quote for assembling the board in Request 1, and I want to understand which parts you place and which stay as hand work.
>
> - Files: the C1-05 Gerbers, `c1-placement.csv` and `c1-assembly-bom.csv` (in `docs/c1-assembly-package/`).
> - The board is two-sided: 16 SMD parts on the bottom, 7 through-hole push buttons on the top (B3-B9). The battery holder (BT1), the Raspberry Pi Pico (U1) and the microSD socket (U3) are large parts. The C2 driver (U2) is a separate module soldered on by its castellated edge.
> - X and Y in the placement file are footprint origins, not part centers, and rotation is as saved by the design tool. Please confirm positions and rotation in your preview before building.
> - The Pico footprint's SMD pads sit 0.9 mm further out in the Gerbers than in the design source. Please build from the Gerbers.
> - I have no supplier part numbers from you. Please propose your parts from the manufacturer part numbers in the BOM, and tell me about every substitution before you order parts.
>
> Please quote each route below, with itemized costs: PCB, components, assembly, setup and engineering, stencil, shipping, tax or import charges, lead time and minimum quantities.
>
> - **Route A: full.** You place all SMD parts and also fit the through-hole buttons, the battery holder, the Pico and the C2 module.
> - **Route B: partial.** You place the SMD parts only. I fit the through-hole buttons, the battery holder, the Pico and the C2 module.
> - **Route C: bare board.** No assembly (Request 1 only).
>
> For each route, quantities 1, 9 and 10. Please also say what happens to excess boards and parts, and which parts have a minimum order.
>
> Questions: which of the large or through-hole parts do you place? Do you offer two-sided assembly in one run? Can you add an inspection photo or a continuity or shorts test and price it separately?

Which parts the factory fits drives the second question to you: for Route B, the checklist treats the hand work as yours.

## Request 3: C2 driver module, assembled (JLCPCB, C2-03 package)

> Please quote the castellated e-paper driver module as a finished assembly, delivered to [delivery address], United States.
>
> - Files: the three files from `Fabrication Files/Castellated E-Paper Driver/OSO-BOOK-C2-03 (JLCPCB)` at commit `6bb483f`: `OSO-BOOK-C2-03-BOM.csv`, `OSO-BOOK-C2-03-PNP.csv` and `OSO-BOOK-C2-03.zip`.
> - Board: 17.272 x 23.876 mm, castellated edge holes, 1.0 mm thick, lead-free HASL.
> - Quantities: 1, 9 and 10.
>
> Please itemize fabrication, the castellation charge, components, assembly, setup, shipping, tax or import charges and lead time, and say whether quantity 9 ordered later repeats setup.
>
> Optional variants, each priced as a change to the BOM above. Please answer whether each is possible, not just the price:
> 1. As published: R1 0.47 ohm in 0402, L1 10 uH in 0805.
> 2. R1 changed to 2.2 ohm in the same 0402 footprint.
> 3. L1 changed to 47 uH rated about 500 mA, if a part exists that fits the 0805 pads (1.2 x 1.3 mm pads, 2.03 mm pitch). If not, say what the largest suitable value is.
>
> Note that the board has no footprint for a pull-down resistor, so a pull-down cannot be added by BOM change.

Variants 2 and 3 only make sense if the pilot or further checking says the published values are wrong. Send variant 1 alone if you want the simplest quote.

## Comparison table (fill in as answers arrive)

Every cell starts Open. One table per maker. Rows are cost lines; columns are the two sequences.

| Cost line | Pilot (qty 1) | Then nine (qty 9) | Ten at once (qty 10) |
| --- | --- | --- | --- |
| C1 PCB fabrication | Open | Open | Open |
| C1 assembly: components | Open | Open | Open |
| C1 assembly: labor | Open | Open | Open |
| C2 module: fabrication and castellation | Open | Open | Open |
| C2 module: components and assembly | Open | Open | Open |
| Setup and engineering (repeated?) | Open | Open | Open |
| Stencil | Open | Open | Open |
| Shipping to the United States | Open | Open | Open |
| Tax and tariffs | Open | Open | Open |
| Lead time | Open | Open | Open |
| Excess boards and parts | Open | Open | Open |
| **Total** | Open | Open | Open |

Compare the sums: pilot plus nine against ten at once, for each route. Keep the one-time tools (a multimeter at least) out of these totals; the Checklist tab keeps them apart.

## What a maker will probably still ask

- Who supplies the parts (turnkey from the maker, or parts you send) and which grade of parts is acceptable.
- Panelization and board edge rules, solder paste stencil, and whether a test or inspection is wanted.
- The LCSC or distributor numbers this package does not have (a known gap, see above).
- Whether through-hole parts are fitted by them, by hand elsewhere, or by you.

## Before you send any of it

- Fill in the delivery address and a contact. The drafts have none, on purpose.
- Attach the named files. The C1 package CSVs are in `docs/c1-assembly-package/`; the Gerber zips are under `reference/the-open-book/upstream/Fabrication Files/`.
- Decide the C2 variants (Request 3) after reading `docs/gdey-c2-values-check.md`.
- Read the maker's own current rules for castellated holes, two-sided assembly and import charges. They change, and these drafts assume nothing about them.
