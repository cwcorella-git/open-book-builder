# Markdown profile for Open Book content (draft)

Prepared 2026-11-17. This is a specification only: no converter or site code exists. It follows your rulings: versioned custom Markdown is the collection source; a deterministic Pico-ready text file is generated from it for the first pilot; text comes first; categories and tags are set before download; favorites and reading progress live on each microSD card.

Firmware facts below were read from `joeycastillo/libros` at base `3be5d84` with PR #10 and PR #11 merged (local branch `obb-pilot`, `5196839`, in `/data/checkouts/libros`). They are source reading, not behavior seen on a device.

**Changed on 2026-11-17:** there are no product configurations any more (buyers choose collections), so the profile serves one device line. The profile now says what works on **stock firmware** (the pilot) and what needs the **feature firmware** (the other nine, specified in `docs/reader-features-spec.md`, not yet written). Added: the `type:` tag convention, the `_STATE` card file, and the stale page-map rule. The author-facing version of these rules is `docs/author-guide.md`.

## Which firmware does what

| Rule or behavior | Stock libros (the pilot) | Feature firmware (the nine) |
| --- | --- | --- |
| Files in the card root, `.txt`, name under 127 bytes | yes | yes |
| Front matter `TITL`, `AUTH`, `GNRE`, `DESC`, `LANG` | yes | yes |
| Chapters (`0x1E`), italic and bold codes | yes | yes |
| Resume | at Lock or return home only | saved after a delay, every few turns and on sleep |
| Changed text with the same file name | stale page map, wrong pages | page map rebuilt automatically |
| Percent read, favorites, recent first, status | no | yes |
| Tag, type and status filters, sort by title or author | no | yes |
| `_STATE` card file | not used | read and written |

A file written to the rules below works on both. Only the extras on the right need the new firmware, and a stock reader simply ignores them.

## What the firmware does today

| Topic | Behavior in the source |
| --- | --- |
| Which files are books | Files in the card root only, with a `.txt` extension, not starting with `.`. No folders. |
| Book identity | The first 8 bytes of SHA-256 of the **file name**, not the content. Renaming a file makes a new book. |
| File name limit | `char filename[128]`, so keep names under 127 bytes including `.txt`. |
| Library index | `_LIBRARY` is rebuilt by a full scan. Carrying progress over a rescan is a TODO in the code. `_LIBBACK` and `_LIBTEMP` are temporary. |
| Front matter | If the file starts with `---` and a newline, lines of the form `KEY: value` follow until another `---` line. Keys are exactly four characters: `TITL`, `AUTH`, `GNRE`, `DESC`, `LANG`. Other keys are skipped. The parser reads until it finds `:` and a newline with no bounds checks, so malformed front matter can hang it. |
| No front matter | The title is the first line, cut at 32 characters. |
| Chapters | A line starting with the Record Separator (0x1E) is a chapter title page, drawn at double size. |
| Emphasis | Shift In (0x0F) steps plain, italic, bold, bold and italic. Shift Out (0x0E) steps bold and italic to bold, and bold or italic to plain. Other control characters below 0x20 are skipped. |
| Line ends | Both `\n` and `\r` end a paragraph, so CRLF files get a blank gap. |
| Pagination | `<name>.pag` is built on first open, using a fixed 288 x 384 pixel page, 18 px per line and 8 px per paragraph. It is never rebuilt: the check is only that the file exists. |
| Progress | `<name minus txt>obp` holds one 32-bit page number. It is written only when the Lock button is pressed or when you return home, by truncating the file and then writing 4 bytes. |
| Percent read | The reader draws a bar and `page/total` from the page number and the `.pag` page count. The book list does not show it. |
| Favorites | None. `BookRecord.flags` exists and nothing uses it. |
| Genre | `GNRE` is stored in the library record. No filter or sort by genre was found in the list screen. |
| Display chunking | Layout works on 127-byte windows. A run of 127 bytes without a space or newline, such as a long URL, is not handled well (a FIXME in the code). |

## The profile

### Source file (the collection)

One Markdown file per work, UTF-8, LF line ends, with a YAML-style header:

```
---
id: moby-dick            # required. a-z, 0-9 and hyphen, at most 80 characters. Never changes.
version: 3               # required. Whole number, raised on every content change.
title: Moby-Dick         # required
type: book               # required: book, article or document
language: en             # required: a language tag
author: Herman Melville  # optional
tags: [fiction, sea]     # optional, assigned here and nowhere else
rights: public domain    # optional, free text
---
```

### Body subset

| Markdown | Device text |
| --- | --- |
| `# Heading` | A chapter: `0x1E`, the heading text, a newline. Keep headings under 100 characters. |
| `## Heading` and below | A bold line of its own. The device has one chapter level. |
| Blank-line-separated paragraphs | One line per paragraph, ended by `\n`. No hard wrapping. |
| `*italic*`, `**bold**` | `0x0F` and `0x0E` sequences. The converter tracks the state so nesting comes out right. |
| `- item` | A line starting `- `. |
| Links | The link text only. The URL is dropped. Whether to keep a list of URLs at the end is open. |
| Block quotes | Plain paragraphs. |

Anything else is **rejected or flagged, never dropped silently**: images, tables, raw HTML, footnotes, math, code blocks, and any run of 127 bytes without a space or newline. The converter prints a report naming each item and its line. A scanned or image-only source cannot be converted; it needs OCR and a human edit first.

### Generated device file

- File name `<id>.txt` in the card root. `.txt` must be exactly the last four characters, because the `.pag` and `.obp` names are derived from them.
- Front matter written in the firmware's own form: `TITL`, `AUTH`, `LANG`, `DESC`, and `GNRE` carrying the tags joined with semicolons. A fixed layout, keys in a fixed order, so the output is byte-for-byte repeatable.
- LF line ends only. Unicode normalized to NFC.
- No size cap is set. Measure a short article, a novel and a long document on the pilot first.

### Tags, types and categories

Tags are set in the source header and exported in `GNRE`, joined with semicolons (`fiction;sea`). The **type** (book, article or document) travels in the same field as a tag with a fixed prefix: `type:article`. One mechanism then serves the tag filter and the type filter and needs no change to the library file layout. The prefix `type:` is reserved; a work has exactly one.

On stock firmware nothing filters on `GNRE`, so tags and types are stored but unused. On the feature firmware the list screen reads them once at scan time and offers a filter. A buyer's card is always the unit of grouping: the site's collections decide which works go on a card.

### Updates, removal and renaming

- Identity is the file name, so keep `<id>.txt` stable across versions.
- **Stock firmware:** a new version must also delete the book's `.pag` file, or the old page map is used on the new text. Whether to keep the old `.obp` is open: a saved page number may point at the wrong place after an edit. The download includes an update note listing the `.pag` and `.obp` files to delete for each changed book.
- **Feature firmware:** the page-map header stores the file size and a checksum of the first and last 4 KB, and the map is rebuilt when they differ, so no manual deletion is needed. The saved page is kept only if it is still inside the new page count; otherwise it resets to the start. That rule is a proposal.
- Renaming a file loses its progress and favorites. Removing a book leaves its `.pag` and `.obp` behind (and its row in `_STATE`); deleting them is manual for now.

### Per-card state

Stock firmware keeps progress in `.obp` files only. The feature firmware adds `_STATE`: a small file in the card root with one record per book, keyed by the same 8-byte name hash the firmware already uses. A record holds the favorite flag, the finished flag, an open counter for "recent first", the saved page, one bookmark page and the cached page count. It is written to a temporary file and renamed over `_STATE`, the way `_LIBRARY` is swapped today, so a power cut leaves the old file whole. The layout is in `docs/reader-features-spec.md`. Both are proposals and need firmware code.

### Percent read in the book list

Computable on the device from the `.obp` page number and the `.pag` page count. Layout depends on the font data and the page metrics above, so a converter cannot reliably precompute page counts. Leave it to the device, and rebuild `.pag` when the text or layout changes.

## Gaps the current (stock) firmware leaves

The feature firmware in `docs/reader-features-spec.md` is meant to close items 1 to 3. None of it is written.


1. The `.pag` file is never invalidated.
2. Progress is saved only on Lock or return home, so a battery pull while reading loses position since the last save. A power cut during the 4-byte write leaves an empty file, which reads back as page 0.
3. No favorites, no tag filter, no percent in the list.
4. The front matter parser has no bounds checks, so the converter must validate its own output strictly.
5. Layout and the limit on listed books have not been seen on a device. The creator's 2022 guide mentions a limit of 15 listed works; the source read here shows no such constant, so test it.

## Open decisions

- The tag vocabulary, multiple-tag rules and display labels, and how untagged personal files are treated.
- Whether links keep their URLs in an end list.
- What happens to `.obp` when a book's version changes.
- Whether the saved page survives a text update when it is still inside the new page count, or always resets (the feature firmware section proposes keeping it).
- Whether `type:` is the right carrier for the type, or a fifth front matter key is worth a library file version bump.
- File and page limits, once sample works have been measured on a pilot reader.
