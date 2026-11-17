# Collections site (design draft)

Prepared 2026-11-17, answers added the same day. This is a design with a localhost mockup (`scripts/build_site.py`, output in `site/_out/`, run with `python3 -m http.server`) and nothing public: the converter and a card tool exist. It says what the site would do, what it depends on, and what only you can decide. Facts about the reader come from `docs/markdown-profile.md` and `docs/reader-features-spec.md`, which were read from the firmware source and not seen on a device.

## What it is for

- A buyer chooses which collections are preloaded on the microSD card that comes with their reader.
- Anyone can download more works from the official site later and copy them to the card.
- Authors and curators get a formatting guide (`docs/author-guide.md`).

There are no product configurations. One reader, one firmware line, and the card's contents are the choice.

## The people involved

- **Curator:** decides what is in a collection. At the moment that is you.
- **Author or submitter:** writes or converts a work to the profile. Only you, for now: outsiders do not submit (answer 1).
- **Buyer:** picks collections on Etsy, where the readers are sold for now (answer 2).
- **Owner preparing a card:** you, for the first ten. You build and flash units and prepare cards on Linux.

## Content model

**Work.** One Markdown file with the profile header (`id`, `version`, `title`, `type`, `language`, optional `author`, `tags`, `rights`). The source of truth is a git repository of these files, so the history is the version record. A work without `rights` is refused.

**Collection.** A small file listing work ids, with a title, a short description and tags:

```
id: starter-fiction
title: Starter fiction
description: Short stories in the public domain.
works: [lighthouse, moby-dick]
```

The site shows each collection's work count and total size, taken from the generated files. The reader shows no images, so collections have none.

**Release notes.** Every changed work gets a line in a changelog: id, old and new version, what changed. This feeds the update note below.

## What the build produces

A converter (`src/open_book_builder/convert/`, specified in the Markdown profile) turns each work into the reader's file and prints a report of anything it rejected. From that the site builds:

- **A single work:** `<id>.txt`.
- **A collection package:** a zip with every work's `.txt`, a short `README.txt` ("copy these files to the top folder of the card"), and an update note.
- **An update note** for stock firmware: the `.pag` and `.obp` files to delete for each changed work, because stock firmware never rebuilds a stale page map. The feature firmware makes this note unnecessary.

## A card preparation tool for Linux

`scripts/prepare_card.py` (standard library only) is a small script for the owner: given a mounted, already formatted card, it copies `babel.bin` and the chosen works or zip packages to the top folder. It prints a plan by default and copies only with `--write`. It has never touched a real card. The rules it follows (formatting is left out of the tool: format FAT32 with your disk tool first):

- It never formats anything by default. Formatting is a separate, explicit option that names the device and asks for confirmation.
- It refuses a device that is not removable or that holds files it does not recognize.
- It checks free space before copying and verifies the copy afterwards.

A selection file (a list of collection ids) lets the same tool prepare many cards.

## How a buyer's choice travels

Readers are sold on Etsy for now. The buyer names the collections there (an order note or a message), and you copy the ids by hand into a selection file that the card tool reads (`--select`). There is no ordering flow on the site, and none is planned. For an order: write the collection ids into a file (one per line), then run `python3 scripts/prepare_card.py <card folder> --site site/_out --select order.txt --babel babel.bin` and add `--write` once the plan looks right. The tool checks every package and work against the site's `index.json` and refuses a stale or damaged one. The design only needs the choice to end up as a list of collection ids.

## Hosting

**Recommended: a static site generated from the repository.** Pages for collections and works, downloads as plain files, the formatting guide, no accounts, no database. Git is the version history and the review tool. It is cheap, easy to move, and has almost nothing to attack.

You curate every work, so no upload service is needed. Add one only if that changes. That service would run the converter on each upload and hold results for review. It is a much bigger project than the static site and not needed for the first ten.

## What it depends on

- The converter and validator (written; the firmware has never loaded its output).
- The feature firmware for the page-map fix, favorites, tags and filters (not written). The site works without it, but the update note then matters.
- `babel.bin`, the font file the reader loads on first boot (GNU Unifont data packed by the original Open Book project). You chose to rebuild it from Unifont rather than redistribute theirs. `scripts/build_babel.py` does that (see "Rebuilding babel.bin" below). The card tool takes the result with `--babel`.
- The author guide (written, untested by an author who is not you).
- Measurements from the pilot: card size, number of works that list well, how long a long work takes to open the first time.

## Rights and sourcing

Each work carries its `rights` text, and the site shows it. The old assembly notes mention a tool, `libros-convert`, that turns Standard Ebooks EPUBs into the reader's format; Standard Ebooks publishes public-domain works. This design does not assume what any source allows. Checking each source's terms is a task for every collection.

## Answers (2026-11-17)

1. **Curation:** you curate only, and outsiders do not submit. A static site, no upload service.
2. **Buyer's choice:** readers are sold on Etsy for now; the buyer picks the collections there and you put them on the card.
3. **`babel.bin`:** rebuild it from Unifont (row 45). Not redistributing the original.
4. **Domain:** you own one to use later. Until then, localhost mockups only.
5. **Language:** English only for the guide and the site's own pages. Works can be in any language the font covers.
6. **Plain copy:** yes. Each work also gets a text-only reading copy with no header, from the same source.

Still open: the tag vocabulary, and the rights check for every source collection.

## Rebuilding babel.bin

`scripts/build_babel.py --hex unifont_all-<version>.hex --ucd <folder> -o babel.bin` writes a 2 MiB file in the layout `BabelDevice.cpp` reads (the byte layout is in the script's docstring). The inputs are Unifont's `.hex` file from ftp.gnu.org/gnu/unifont and three Unicode data files (`LineBreak.txt`, `BidiMirroring.txt`, `UnicodeData.txt`) of the same Unicode version as the Python running it; the script refuses a mismatch. The glyph bytes are Unifont's hex bytes unchanged.

How it was checked: the original `babel.bin` was used as a reference and never kept. With Unifont 15.1.05 and Unicode 15.0, over the 55,445 code points both files list, the character class, bidi class, whitespace, control, line-break, strong-direction and mirroring flags and every case mapping that both have match exactly. The differences left are version drift: 12,487 glyph shapes (the original was drawn from an older Unifont), 23 glyph widths, one reclassified character (U+1734), 189 code points the original does not list (and 2 that only it lists), and eight more case and mirroring pairs from newer Unicode data. `scripts/compare_babel.py mine.bin original.bin` prints this. Several rules were inferred from the original, not from the source (which code points are left out: unassigned and private use except U+E000 and U+F8FF; which line-break classes allow a break; which characters are control or whitespace; strong direction for combining marks in right-to-left blocks), and are marked as inferred in the script. The original also holds a type 64 table that the firmware ignores, and the rebuilt file omits it.

Not done: the file has never been loaded by the firmware or a reader. The reader mirror in the script (`BabelReader`) follows `BabelDevice` step by step, but it is Python, not the firmware. A pilot reader is the real test.

**License, not decided:** Unifont's README (15.1.05) says the compiled fonts are GNU GPL version 2 or later with the GNU font embedding exception for documents that use the font. Whether a `babel.bin` counts as such a document or as a derived font file, and what that means for selling or giving away cards that hold it, is a legal question this design does not answer. Shipping the script and the Unifont `.hex` file next to the card would make the source available either way.

## Not in this design

Accounts, payments, a mobile app, image support, wireless download to the reader (deferred by ruling), and anything about the reader's firmware beyond what the other two documents already specify.
