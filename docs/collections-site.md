# Collections site (design draft)

Prepared 2026-11-17. This is a design only: no site exists; the converter and a card tool do. It says what the site would do, what it depends on, and what only you can decide. Facts about the reader come from `docs/markdown-profile.md` and `docs/reader-features-spec.md`, which were read from the firmware source and not seen on a device.

## What it is for

- A buyer chooses which collections are preloaded on the microSD card that comes with their reader.
- Anyone can download more works from the official site later and copy them to the card.
- Authors and curators get a formatting guide (`docs/author-guide.md`).

There are no product configurations. One reader, one firmware line, and the card's contents are the choice.

## The people involved

- **Curator:** decides what is in a collection. At the moment that is you.
- **Author or submitter:** writes or converts a work to the profile. Whether outsiders can submit is open.
- **Buyer:** picks collections.
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

The first ten are made by you, so the choice can be a list in a message or a form response. A real ordering flow is a separate decision (see the questions). The design only needs the choice to end up as a list of collection ids that the card tool reads.

## Hosting

**Recommended: a static site generated from the repository.** Pages for collections and works, downloads as plain files, the formatting guide, no accounts, no database. Git is the version history and the review tool. It is cheap, easy to move, and has almost nothing to attack.

Add a service only if outsiders must upload works through the site. That service would run the converter on each upload and hold results for review. It is a much bigger project than the static site and not needed for the first ten.

## What it depends on

- The converter and validator (written; the firmware has never loaded its output).
- The feature firmware for the page-map fix, favorites, tags and filters (not written). The site works without it, but the update note then matters.
- `babel.bin`, the font file the reader loads on first boot. It currently comes from the original project's page. Whether and how we may redistribute it is not checked.
- The author guide (written, untested by an author who is not you).
- Measurements from the pilot: card size, number of works that list well, how long a long work takes to open the first time.

## Rights and sourcing

Each work carries its `rights` text, and the site shows it. The old assembly notes mention a tool, `libros-convert`, that turns Standard Ebooks EPUBs into the reader's format; Standard Ebooks publishes public-domain works. This design does not assume what any source allows. Checking each source's terms is a task for every collection.

## Questions for you

1. Who curates, and can outsiders submit works? That decides static site or upload service.
2. Where is the buyer's choice captured, and how are the readers sold? The design has no answer yet.
3. May we redistribute `babel.bin`, and who asks the original project?
4. Do you want a domain of your own for this, or a page on an existing site? (The old Pages site for the app is gone.)
5. Which languages should the guide and the site's own pages be written in first?
6. Should downloads include a text-only reading copy (plain `.txt` without front matter) for people who want to read on another device?

## Not in this design

Accounts, payments, a mobile app, image support, wireless download to the reader (deferred by ruling), and anything about the reader's firmware beyond what the other two documents already specify.
